"""Measurements on a committed coupled-cell mesh, and on the size field.

The ladder moved the eigenfrequencies by tens of percent without settling, and
the fluxonium-like mode's stiffness is almost entirely the lumped port's
boundary term. That makes the port face's discretisation the thing to measure,
so this module measures it: what is actually in the mesh file, rather than what
the size prescription asked for.

Two halves, deliberately separate:

* :func:`inspect_mesh` reads a committed MSH 2.2 file and reports the port
  faces, their tags, area, orientation, the elements covering them and their
  quality, and the same for the conductor sheet. No gmsh, no geometry kernel,
  no re-meshing - it is a measurement of the evidence on disk.
* :func:`classify_size_field_curves` rebuilds the OCC model with the mesher's
  own code and reports which curves the Distance field actually sees. That
  needs gmsh but never meshes, so it is cheap and it cannot perturb a record.

``h_gap`` is what the rule asks for at the conductor and etch edges. It is not
what the mesh has on the port face, and the difference is the point:
:class:`PortFaceMeasurement` reports both and never conflates them.
"""

from __future__ import annotations

import itertools
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

#: MSH 2.2 element type numbers used by the coupled cell.
_TRIANGLE = 2
_TETRAHEDRON = 4

Point = tuple[float, float, float]


class MeshInspectionError(RuntimeError):
    """The mesh file is not the MSH 2.2 the coupled mesher writes."""


@dataclass(frozen=True)
class Mesh:
    """Just enough of an MSH 2.2 file to measure it."""

    path: Path
    nodes: dict[int, Point]
    triangles: dict[int, list[tuple[int, int, int]]]
    tetrahedra: dict[int, list[tuple[int, int, int, int]]]
    physical_names: dict[int, str]

    @property
    def bounding_box(self) -> tuple[Point, Point]:
        xs = [p[0] for p in self.nodes.values()]
        ys = [p[1] for p in self.nodes.values()]
        zs = [p[2] for p in self.nodes.values()]
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    @property
    def largest_extent(self) -> float:
        """Palace's ``Lc`` in mesh length units (``iodata.cpp:452-464``)."""
        lo, hi = self.bounding_box
        return max(hi[i] - lo[i] for i in range(3))


def read_msh2(path: Path | str) -> Mesh:
    """Parse the MSH 2.2 ASCII the coupled mesher writes."""
    path = Path(path)
    nodes: dict[int, Point] = {}
    triangles: dict[int, list[tuple[int, int, int]]] = {}
    tetrahedra: dict[int, list[tuple[int, int, int, int]]] = {}
    names: dict[int, str] = {}
    with path.open() as handle:
        lines = iter(handle)
        for raw in lines:
            section = raw.strip()
            if section == "$MeshFormat":
                version = next(lines).split()[0]
                if not version.startswith("2.2"):
                    raise MeshInspectionError(f"{path}: expected MSH 2.2, got {version}")
            elif section == "$PhysicalNames":
                for _ in range(int(next(lines))):
                    parts = next(lines).split(maxsplit=2)
                    names[int(parts[1])] = parts[2].strip().strip('"')
            elif section == "$Nodes":
                for _ in range(int(next(lines))):
                    parts = next(lines).split()
                    nodes[int(parts[0])] = (float(parts[1]), float(parts[2]), float(parts[3]))
            elif section == "$Elements":
                for _ in range(int(next(lines))):
                    parts = [int(x) for x in next(lines).split()]
                    element_type, n_tags = parts[1], parts[2]
                    physical = parts[3] if n_tags else 0
                    connectivity = parts[3 + n_tags:]
                    if element_type == _TRIANGLE:
                        triangles.setdefault(physical, []).append(tuple(connectivity[:3]))  # type: ignore[arg-type]
                    elif element_type == _TETRAHEDRON:
                        tetrahedra.setdefault(physical, []).append(tuple(connectivity[:4]))  # type: ignore[arg-type]
    if not nodes:
        raise MeshInspectionError(f"{path}: no nodes")
    return Mesh(path=path, nodes=nodes, triangles=triangles, tetrahedra=tetrahedra, physical_names=names)


def _triangle_area_and_normal(a: Point, b: Point, c: Point) -> tuple[float, Point]:
    u = tuple(b[i] - a[i] for i in range(3))
    v = tuple(c[i] - a[i] for i in range(3))
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    norm = math.sqrt(sum(x * x for x in n))
    if norm == 0.0:
        return 0.0, (0.0, 0.0, 0.0)
    return 0.5 * norm, tuple(x / norm for x in n)  # type: ignore[return-value]


def _triangle_quality(a: Point, b: Point, c: Point) -> float:
    """``2 r_in / r_circ``: 1 for an equilateral triangle, 0 for a degenerate one."""
    lengths = [math.dist(b, c), math.dist(a, c), math.dist(a, b)]
    area, _ = _triangle_area_and_normal(a, b, c)
    if area <= 0.0:
        return 0.0
    semi = sum(lengths) / 2.0
    r_in = area / semi
    r_circ = lengths[0] * lengths[1] * lengths[2] / (4.0 * area)
    return 2.0 * r_in / r_circ


@dataclass(frozen=True)
class FaceMeasurement:
    """Measured, per physical surface tag."""

    tag: int
    name: str
    n_triangles: int
    area: float
    normals: tuple[Point, ...]
    edge_length_min: float
    edge_length_max: float
    edge_length_mean: float
    quality_min: float
    quality_mean: float
    bounding_box: tuple[Point, Point]

    @property
    def equivalent_size(self) -> float:
        """Side of the equilateral triangle of the mean element area."""
        if self.n_triangles == 0:
            return math.inf
        return math.sqrt(4.0 * (self.area / self.n_triangles) / math.sqrt(3.0))

    @property
    def is_planar(self) -> bool:
        return len(self.normals) == 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "name": self.name,
            "triangles": self.n_triangles,
            "area_mm2": self.area,
            "planar": self.is_planar,
            "unit_normals": [list(n) for n in self.normals],
            "edge_length_mm": {
                "min": self.edge_length_min,
                "mean": self.edge_length_mean,
                "max": self.edge_length_max,
            },
            "equivalent_element_size_mm": self.equivalent_size,
            "quality_2rin_over_rcirc": {"min": self.quality_min, "mean": self.quality_mean},
            "bounding_box_mm": {"min": list(self.bounding_box[0]), "max": list(self.bounding_box[1])},
        }


def measure_face(mesh: Mesh, tag: int, *, normal_tolerance: float = 1.0e-9) -> FaceMeasurement:
    """Area, orientation, element coverage and quality of one physical surface."""
    connectivity = mesh.triangles.get(tag, [])
    if not connectivity:
        raise MeshInspectionError(f"{mesh.path}: physical surface {tag} has no triangles")
    area = 0.0
    normals: set[Point] = set()
    lengths: list[float] = []
    qualities: list[float] = []
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for conn in connectivity:
        p = tuple(mesh.nodes[i] for i in conn)
        a, n = _triangle_area_and_normal(*p)
        area += a
        normals.add(tuple(round(abs(x) / normal_tolerance) * normal_tolerance for x in n))  # type: ignore[arg-type]
        qualities.append(_triangle_quality(*p))
        for i, j in itertools.combinations(range(3), 2):
            lengths.append(math.dist(p[i], p[j]))
        for point in p:
            for k in range(3):
                lo[k] = min(lo[k], point[k])
                hi[k] = max(hi[k], point[k])
    return FaceMeasurement(
        tag=tag,
        name=mesh.physical_names.get(tag, f"tag {tag}"),
        n_triangles=len(connectivity),
        area=area,
        normals=tuple(sorted(normals)),
        edge_length_min=min(lengths),
        edge_length_max=max(lengths),
        edge_length_mean=sum(lengths) / len(lengths),
        quality_min=min(qualities),
        quality_mean=sum(qualities) / len(qualities),
        bounding_box=(tuple(lo), tuple(hi)),  # type: ignore[arg-type]
    )


@dataclass(frozen=True)
class PortFaceMeasurement:
    """The port face, with what was asked for kept apart from what was built."""

    face: FaceMeasurement
    requested_h_gap_mm: float
    length_mm: float
    width_mm: float

    @property
    def elements_across_width(self) -> float:
        """How many elements the mean size fits across the narrow dimension."""
        return self.width_mm / self.face.equivalent_size

    @property
    def resolution_ratio(self) -> float:
        """Measured element size on the face, over the requested ``h_gap``.

        Above 1 means the face is coarser than the rule asked for. This is the
        distinction the ladder never made: ``h_gap`` is prescribed *at the
        conductor and etch curves*, and the port face's interior is not on one.
        """
        return self.face.equivalent_size / self.requested_h_gap_mm

    @property
    def longest_edge_over_h_gap(self) -> float:
        return self.face.edge_length_max / self.requested_h_gap_mm

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.face.as_dict(),
            "declared_length_mm": self.length_mm,
            "declared_width_mm": self.width_mm,
            "declared_area_mm2": self.length_mm * self.width_mm,
            "requested_h_gap_mm": self.requested_h_gap_mm,
            "measured_over_requested": {
                "equivalent_element_size_over_h_gap": self.resolution_ratio,
                "longest_edge_over_h_gap": self.longest_edge_over_h_gap,
                "note": (
                    "h_gap is the size prescribed AT the conductor and etch curves. The "
                    "port face's own curves are not all in the Distance field and its "
                    "interior is up to width/2 away from those that are, so this ratio "
                    "is not expected to be 1 and measuring it is the point."
                ),
            },
            "elements_across_width": self.elements_across_width,
        }


def size_field_profile(h_gap_mm: float, h_far_mm: float, halo_mm: float, distance_mm: float) -> float:
    """gmsh's Threshold field: linear from ``h_gap`` at 0 to ``h_far`` at ``halo``."""
    if distance_mm <= 0.0:
        return h_gap_mm
    if distance_mm >= halo_mm:
        return h_far_mm
    return h_gap_mm + (h_far_mm - h_gap_mm) * (distance_mm / halo_mm)


def distance_at_which_size_doubles(h_gap_mm: float, h_far_mm: float, halo_mm: float) -> float:
    """How far from a field curve the prescribed size is still within 2x ``h_gap``.

    The blend is linear, so this is ``halo * h_gap / (h_far - h_gap)``. Compare
    it with half the port width: if it is smaller, the middle of the port face
    is prescribed a size the face cannot accommodate, at every ladder level,
    because ``h_gap``, ``h_far`` and the halo do not all scale together.
    """
    if h_far_mm <= h_gap_mm:
        return math.inf
    return halo_mm * h_gap_mm / (h_far_mm - h_gap_mm)


def inspect_mesh(
    path: Path | str,
    *,
    requested_h_gap_mm: float,
    port_tags: dict[str, int],
    port_dimensions: dict[str, tuple[float, float]],
    other_tags: Iterable[int] = (),
) -> dict[str, Any]:
    """Measure one committed mesh: ports, sheets, counts and the bounding box."""
    mesh = read_msh2(path)
    lo, hi = mesh.bounding_box
    report: dict[str, Any] = {
        "mesh": str(path),
        "nodes": len(mesh.nodes),
        "triangles": sum(len(v) for v in mesh.triangles.values()),
        "tetrahedra": sum(len(v) for v in mesh.tetrahedra.values()),
        "physical_names": dict(sorted(mesh.physical_names.items())),
        "bounding_box_mm": {"min": list(lo), "max": list(hi)},
        "largest_extent_mm": mesh.largest_extent,
        "Lc_m_implied": mesh.largest_extent * 1.0e-3,
        "tetrahedra_by_tag": {
            mesh.physical_names.get(t, str(t)): len(v) for t, v in sorted(mesh.tetrahedra.items())
        },
        "ports": {},
        "surfaces": {},
    }
    for name, tag in port_tags.items():
        length_mm, width_mm = port_dimensions[name]
        report["ports"][name] = PortFaceMeasurement(
            face=measure_face(mesh, tag),
            requested_h_gap_mm=requested_h_gap_mm,
            length_mm=length_mm,
            width_mm=width_mm,
        ).as_dict()
    for tag in other_tags:
        measurement = measure_face(mesh, tag)
        report["surfaces"][measurement.name] = measurement.as_dict()
    return report


def compare_across_levels(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Are the material and boundary assignments the same at every level?

    A refinement study is only a refinement study if the model did not change.
    """
    consistency: dict[str, Any] = {}
    names = {level: tuple(sorted(r["physical_names"].items())) for level, r in reports.items()}
    consistency["physical_names_identical"] = len(set(names.values())) == 1
    consistency["physical_names_by_level"] = {k: dict(v) for k, v in names.items()}

    boxes = {level: (tuple(r["bounding_box_mm"]["min"]), tuple(r["bounding_box_mm"]["max"]))
             for level, r in reports.items()}
    consistency["bounding_box_identical"] = len(set(boxes.values())) == 1
    consistency["largest_extent_mm"] = {k: r["largest_extent_mm"] for k, r in reports.items()}

    areas: dict[str, dict[str, float]] = {}
    for level, report in reports.items():
        for port, measurement in report["ports"].items():
            areas.setdefault(port, {})[level] = measurement["area_mm2"]
        for surface, measurement in report["surfaces"].items():
            areas.setdefault(surface, {})[level] = measurement["area_mm2"]
    consistency["areas_mm2"] = areas
    # Relative, not absolute: the outer box is 62.88 mm^2 and summing tens of
    # thousands of triangle areas in a different order moves the last bit.
    consistency["area_relative_tolerance"] = 1.0e-9
    consistency["areas_identical"] = {
        name: (max(by_level.values()) - min(by_level.values()))
        <= 1.0e-9 * max(abs(v) for v in by_level.values())
        for name, by_level in areas.items()
    }
    normals: dict[str, set[Any]] = {}
    for level, report in reports.items():
        for port, measurement in report["ports"].items():
            normals.setdefault(port, set()).add(tuple(tuple(n) for n in measurement["unit_normals"]))
    consistency["port_orientation_identical"] = {k: len(v) == 1 for k, v in normals.items()}
    consistency["verdict"] = (
        "MODEL UNCHANGED ACROSS LEVELS"
        if consistency["physical_names_identical"]
        and consistency["bounding_box_identical"]
        and all(consistency["areas_identical"].values())
        and all(consistency["port_orientation_identical"].values())
        else "MODEL DIFFERS ACROSS LEVELS - the ladder is not a refinement study"
    )
    return consistency


def classify_size_field_curves(cell: Any, level: int, halo_mm: float) -> dict[str, Any]:
    """Which curves the Distance field sees, and which port curves are missing.

    Rebuilds the OCC model exactly as :func:`solvers.palace.coupled_mesh.dry_run`
    does, up to the point where ``field_curves`` is assembled, and stops. No
    mesh is generated and no file is written.

    The mesher classifies a planar face, and when it is a port face it
    ``continue``s before collecting that face's curves. Whether that omits
    anything depends on the neighbours: a port curve shared with a conductor or
    etch face is collected from the other side. This reports, per curve,
    whether it is in the field and what its other neighbour is, so the question
    is answered by measurement rather than by reading the ``continue``.
    """
    from solvers.palace.coupled_mesh import (  # noqa: PLC0415
        MODEL_NAME,
        _bbox_inside,
        _is_plane_face,
        _require_gmsh,
        mesh_sizes_mm,
    )

    gmsh = _require_gmsh()
    _, h_gap, h_far = mesh_sizes_mm(cell, level)
    z0 = cell.z_chip_top_mm
    ports_in_order = [
        ("port_F1", cell.ports["P_F1"][0]),
        ("port_R1_a", cell.ports["P_R1"][0]),
        ("port_R1_b", cell.ports["P_R1"][1]),
    ]
    conductor_rects = cell.all_conductor_rects()
    etch_rects = list(cell.etch)

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add(f"{MODEL_NAME}_curve_inspection")
        occ = gmsh.model.occ
        dx, dy = cell.x_size_mm, cell.y_size_mm
        substrate = occ.addBox(
            cell.x_min_mm, cell.y_min_mm, cell.z_substrate_bottom_mm, dx, dy,
            z0 - cell.z_substrate_bottom_mm,
        )
        vacuum = occ.addBox(cell.x_min_mm, cell.y_min_mm, z0, dx, dy, cell.z_lid_mm - z0)
        tools = [
            (2, occ.addRectangle(r.x_min, r.y_min, z0, r.w_mm, r.h_mm))
            for r in [*etch_rects, *conductor_rects, *(p for _, p in ports_in_order)]
        ]
        occ.fragment([(3, substrate), (3, vacuum)], tools)
        occ.synchronize()

        face_class: dict[int, str] = {}
        port_faces: dict[str, list[int]] = {name: [] for name, _ in ports_in_order}
        field_curves: set[int] = set()
        for dim, tag in gmsh.model.getEntities(2):
            bbox = gmsh.model.getBoundingBox(dim, tag)
            if not _is_plane_face(bbox, z0):
                continue
            port_name = next((n for n, r in ports_in_order if _bbox_inside(bbox, r)), None)
            if port_name is not None:
                port_faces[port_name].append(tag)
                face_class[tag] = f"port:{port_name}"
                continue
            in_conductor = any(_bbox_inside(bbox, r) for r in conductor_rects)
            in_etch = any(_bbox_inside(bbox, r) for r in etch_rects)
            face_class[tag] = "conductor" if in_conductor else ("etch" if in_etch else "ground_plane")
            if in_conductor or in_etch:
                for _, curve in gmsh.model.getBoundary([(2, tag)], oriented=False):
                    field_curves.add(int(curve))

        ports: dict[str, Any] = {}
        for name, faces in port_faces.items():
            curves: list[dict[str, Any]] = []
            for face in faces:
                for _, curve in gmsh.model.getBoundary([(2, face)], oriented=False):
                    curve = int(curve)
                    neighbours = [
                        face_class.get(int(t), "not-in-plane")
                        for t in gmsh.model.getAdjacencies(1, curve)[0]
                        if int(t) != face
                    ]
                    box = gmsh.model.getBoundingBox(1, curve)
                    curves.append({
                        "curve": curve,
                        "in_distance_field": curve in field_curves,
                        "contributed_by": [n for n in neighbours if n in ("conductor", "etch")],
                        "other_neighbours": neighbours,
                        "bounding_box_mm": {"min": list(box[:3]), "max": list(box[3:])},
                    })
            missing = [c for c in curves if not c["in_distance_field"]]
            ports[name] = {
                "occ_faces": faces,
                "curves": curves,
                "curves_total": len(curves),
                "curves_in_field": len(curves) - len(missing),
                "curves_missing": [c["curve"] for c in missing],
                "missing_curve_neighbours": sorted({n for c in missing for n in c["other_neighbours"]}),
            }
        classes = Counter(v.split(":")[0] for v in face_class.values())
    finally:
        gmsh.finalize()

    half_widths = {
        "port_F1": min(cell.ports["P_F1"][0].w_mm, cell.ports["P_F1"][0].h_mm) / 2.0,
    }
    reach = distance_at_which_size_doubles(h_gap, h_far, halo_mm)
    centre_size = size_field_profile(h_gap, h_far, halo_mm, half_widths["port_F1"])
    port_width = min(cell.ports["P_F1"][0].w_mm, cell.ports["P_F1"][0].h_mm)
    return {
        "level": level,
        "halo_mm": halo_mm,
        "h_gap_mm": h_gap,
        "h_far_mm": h_far,
        "planar_faces_at_z0": len(face_class),
        "face_classes": dict(classes),
        "field_curves_total": len(field_curves),
        "ports": ports,
        "size_field": {
            "profile": "gmsh Threshold, linear from h_gap at distance 0 to h_far at the halo",
            "gradient_mm_per_mm": (h_far - h_gap) / halo_mm,
            "distance_at_which_the_prescribed_size_doubles_mm": reach,
            "half_port_width_mm": half_widths["port_F1"],
            "reach_covers_half_the_port_width": reach >= half_widths["port_F1"],
            "prescribed_size_at_port_centre_mm": centre_size,
            "prescribed_size_at_port_centre_over_h_gap": centre_size / h_gap,
            "prescribed_size_at_port_centre_over_port_width": centre_size / port_width,
            "port_width_mm": port_width,
            "note": (
                "The size is prescribed by distance to a Distance-field curve, and the "
                "port face's interior is up to half its width from the nearest one. The "
                "ratio of the prescribed size at the port centre to h_gap is "
                "scale-invariant - h_gap and h_far both carry the level factor while the "
                "halo does not, so the whole profile scales by the level factor and the "
                "ratio does not change with refinement. When the size prescribed at the "
                "centre exceeds the port width, the only thing setting the element count "
                "on the face is the face's own boundary."
            ),
        },
        "early_port_face_continue": {
            "question": (
                "does skipping the port faces when collecting Distance-field curves omit "
                "curves that no other face contributes?"
            ),
            "answer": {
                name: (
                    "no curves missing"
                    if not data["curves_missing"]
                    else f"{len(data['curves_missing'])} of {data['curves_total']} missing, "
                         f"neighbours {data['missing_curve_neighbours']}"
                )
                for name, data in ports.items()
            },
        },
    }


__all__ = [
    "FaceMeasurement",
    "Mesh",
    "MeshInspectionError",
    "PortFaceMeasurement",
    "classify_size_field_curves",
    "compare_across_levels",
    "distance_at_which_size_doubles",
    "inspect_mesh",
    "measure_face",
    "read_msh2",
    "size_field_profile",
]
