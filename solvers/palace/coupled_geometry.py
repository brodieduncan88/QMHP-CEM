"""Planar geometry of the S1 coupled chip cell (checkpoint A, pure Python).

Turns the machine-readable declaration
``config/coupled/v2a_five_node_candidate.json`` (schema
``qmhp-cem.coupled-candidate/0.2.0``) into a :class:`ChipCell`: a set of
axis-aligned rectangles in the z = 0 plane of the spec §7.3 frame (origin at
the centre of the chip top surface, +Z toward the lid), grouped by role.

* **conductors** — zero-thickness PEC metal on the chip: the F1 island, the
  R1 coupling pad and the R1 CPW centre conductor (one rectangle per
  meander segment, plus the short bar at the far end);
* **etch** — regions removed from the ground plane: the island's
  surrounding gap, the coupling pad's surrounding gap and the CPW slot; the
  ground plane is everything else at z = 0;
* **ports** — the lumped-port rectangles ``P_F1`` (the element site across
  the island's -Y gap) and ``P_R1`` (two elements across both CPW gaps
  0.150 mm before the short).

Everything geometric here realises the declaration's unapproved
ENGINEERING-SEED values; nothing is tuned to a result. The meander is
constructed deterministically from the declared path description and the
constants below (``MEANDER_FIRST_STRAIGHT_MM`` is the one value the
declaration's prose leaves implicit and is therefore an ENGINEERING-SEED of
this module). No gmsh, gdsfactory or numpy dependency: this module is the
input to :mod:`solvers.palace.coupled_mesh` and to the geometry preview of
``docs/coupled-candidate/implementation-plan.md`` §4.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

#: Geometric coincidence tolerance (mm). Rectangle edges that meet within
#: this distance are treated as touching, never as overlapping.
TOL_MM = 1.0e-9

#: ENGINEERING-SEED of this module: the straight run along +X from the
#: coupling pad's +X edge before the meander starts (mm). The declaration's
#: path prose ("from R1.coupling_pad along +X, then a meander ...") does not
#: quantify it.
MEANDER_FIRST_STRAIGHT_MM = 0.30

#: Rounding applied to preview coordinates so the preview is byte-stable.
PREVIEW_DECIMALS = 9

_PATH_RE = re.compile(
    r"meander of (?P<leg>[0-9.]+) mm legs along Y with (?P<pitch>[0-9.]+) mm pitch "
    r"inside x in \[(?P<x0>-?[0-9.]+), (?P<x1>-?[0-9.]+)\], "
    r"y in \[(?P<y0>-?[0-9.]+), (?P<y1>-?[0-9.]+)\]"
)


# --- rectangles ---------------------------------------------------------------


@dataclass(frozen=True)
class Rect:
    """Axis-aligned rectangle in the z = 0 plane, by centre and size (mm)."""

    cx_mm: float
    cy_mm: float
    w_mm: float
    h_mm: float

    def __post_init__(self) -> None:
        if not (self.w_mm > 0.0 and self.h_mm > 0.0):
            raise ValueError(f"rectangle sizes must be positive, got {self.w_mm} x {self.h_mm}")

    @classmethod
    def from_bounds(cls, x_min: float, y_min: float, x_max: float, y_max: float) -> "Rect":
        return cls((x_min + x_max) / 2.0, (y_min + y_max) / 2.0, x_max - x_min, y_max - y_min)

    @property
    def x_min(self) -> float:
        return self.cx_mm - self.w_mm / 2.0

    @property
    def x_max(self) -> float:
        return self.cx_mm + self.w_mm / 2.0

    @property
    def y_min(self) -> float:
        return self.cy_mm - self.h_mm / 2.0

    @property
    def y_max(self) -> float:
        return self.cy_mm + self.h_mm / 2.0

    @property
    def area_mm2(self) -> float:
        return self.w_mm * self.h_mm

    def inflate(self, d: float) -> "Rect":
        """The rectangle grown by ``d`` on every side (negative ``d`` shrinks)."""
        return Rect(self.cx_mm, self.cy_mm, self.w_mm + 2.0 * d, self.h_mm + 2.0 * d)

    def contains(self, other: "Rect") -> bool:
        """``other`` lies inside this rectangle (closed; touching edges count)."""
        return (
            other.x_min >= self.x_min - TOL_MM
            and other.x_max <= self.x_max + TOL_MM
            and other.y_min >= self.y_min - TOL_MM
            and other.y_max <= self.y_max + TOL_MM
        )

    def overlaps(self, other: "Rect") -> bool:
        """The interiors intersect (touching along an edge is not overlap)."""
        return (
            other.x_min < self.x_max - TOL_MM
            and other.x_max > self.x_min + TOL_MM
            and other.y_min < self.y_max - TOL_MM
            and other.y_max > self.y_min + TOL_MM
        )

    def polygon(self) -> list[list[float]]:
        """Counter-clockwise corner list, rounded for a byte-stable preview."""
        r = lambda v: round(v, PREVIEW_DECIMALS)  # noqa: E731
        return [
            [r(self.x_min), r(self.y_min)],
            [r(self.x_max), r(self.y_min)],
            [r(self.x_max), r(self.y_max)],
            [r(self.x_min), r(self.y_max)],
        ]


def union_area_mm2(rects: list[Rect]) -> float:
    """Area of the union of axis-aligned rectangles (coordinate compression)."""
    if not rects:
        return 0.0
    xs = sorted({v for r in rects for v in (r.x_min, r.x_max)})
    ys = sorted({v for r in rects for v in (r.y_min, r.y_max)})
    total = 0.0
    for i in range(len(xs) - 1):
        xm = (xs[i] + xs[i + 1]) / 2.0
        for j in range(len(ys) - 1):
            ym = (ys[j] + ys[j + 1]) / 2.0
            if any(r.x_min <= xm <= r.x_max and r.y_min <= ym <= r.y_max for r in rects):
                total += (xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j])
    return total


# --- the chip cell -------------------------------------------------------------


#: Clearance keys of ``geometry.clearances_mm`` and the conductor group each
#: one measures against the four lateral cell walls.
CLEARANCE_TARGETS: dict[str, str] = {
    "island_to_cell_wall_min": "F1.island",
    "meander_to_cell_wall_min": "R1.cpw",
}


@dataclass(frozen=True)
class ChipCell:
    """The bounded S1 chip cell as planar rectangles (spec §7.3 frame, mm)."""

    x_min_mm: float
    x_max_mm: float
    y_min_mm: float
    y_max_mm: float
    z_substrate_bottom_mm: float
    z_chip_top_mm: float
    z_lid_mm: float
    substrate_eps_r: float
    conductors: dict[str, list[Rect]]
    etch: list[Rect]
    ports: dict[str, list[Rect]]
    port_directions: dict[str, list[str]]
    min_gap_mm: float
    resonator_total_length_mm: float
    clearances_mm: dict[str, float] = field(default_factory=dict)
    declared_gaps_mm: dict[str, float] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    # -- derived sizes --------------------------------------------------------

    @property
    def x_size_mm(self) -> float:
        return self.x_max_mm - self.x_min_mm

    @property
    def y_size_mm(self) -> float:
        return self.y_max_mm - self.y_min_mm

    @property
    def cell_rect(self) -> Rect:
        return Rect.from_bounds(self.x_min_mm, self.y_min_mm, self.x_max_mm, self.y_max_mm)

    def all_conductor_rects(self) -> list[Rect]:
        return [r for rects in self.conductors.values() for r in rects]

    def all_port_rects(self) -> list[Rect]:
        return [r for rects in self.ports.values() for r in rects]

    def etched_area_mm2(self) -> float:
        """Area of the union of the etch regions (ground removed), mm^2."""
        return union_area_mm2(self.etch)

    def conductor_area_mm2(self) -> float:
        """Area of the union of the on-chip conductors (not the ground), mm^2."""
        return union_area_mm2(self.all_conductor_rects())

    # -- checks -----------------------------------------------------------------

    def _wall_clearance(self, rects: list[Rect]) -> float:
        return min(
            min(r.x_min - self.x_min_mm, self.x_max_mm - r.x_max, r.y_min - self.y_min_mm, self.y_max_mm - r.y_max)
            for r in rects
        )

    def clearance_report(self) -> list[str]:
        """Violations of the declared clearances and of the planar consistency rules.

        Empty when: every rectangle lies inside the cell; every declared
        ``clearances_mm`` entry holds for its conductor group; no conductor of
        one node overlaps a conductor of another node; every port rectangle
        lies inside an etch region and overlaps no conductor; the realised
        island-to-pad separation equals the declared ``gap_to_island_mm``.
        """
        cell = self.cell_rect
        report: list[str] = []
        for group, rects in self.conductors.items():
            for i, r in enumerate(rects):
                if not cell.contains(r):
                    report.append(f"conductor {group}[{i}] extends outside the cell")
        for i, r in enumerate(self.etch):
            if not cell.contains(r):
                report.append(f"etch[{i}] extends outside the cell")
        for key, declared in self.clearances_mm.items():
            group = CLEARANCE_TARGETS.get(key)
            if group is None or group not in self.conductors:
                report.append(f"clearance {key!r} names no known conductor group")
                continue
            realised = self._wall_clearance(self.conductors[group])
            if realised < declared - TOL_MM:
                report.append(
                    f"clearance {key}: realised {realised:.6f} mm < declared {declared:.6f} mm"
                )
        groups = list(self.conductors.items())
        for a in range(len(groups)):
            for b in range(a + 1, len(groups)):
                name_a, rects_a = groups[a]
                name_b, rects_b = groups[b]
                if name_a.split(".")[0] == name_b.split(".")[0]:
                    continue  # same electrical node: joints overlap by design
                for ra in rects_a:
                    for rb in rects_b:
                        if ra.overlaps(rb):
                            report.append(f"conductor {name_a} overlaps conductor {name_b}")
        for pid, prects in self.ports.items():
            for i, pr in enumerate(prects):
                if not any(e.contains(pr) for e in self.etch):
                    report.append(f"port {pid}[{i}] lies outside every etch region")
                for group, rects in self.conductors.items():
                    if any(pr.overlaps(c) for c in rects):
                        report.append(f"port {pid}[{i}] overlaps conductor {group}")
        gap = self.declared_gaps_mm.get("R1.coupling_pad.gap_to_island_mm")
        if gap is not None and "F1.island" in self.conductors and "R1.coupling_pad" in self.conductors:
            island = self.conductors["F1.island"][0]
            pad = self.conductors["R1.coupling_pad"][0]
            realised = pad.x_min - island.x_max
            if abs(realised - gap) > TOL_MM:
                report.append(
                    f"island-to-pad separation {realised:.6f} mm != declared gap_to_island {gap:.6f} mm"
                )
        return report

    # -- preview ----------------------------------------------------------------

    def preview_polygons(self) -> dict[str, Any]:
        """JSON-able, byte-stable description of every polygon in the §7.3 frame."""
        return {
            "frame": "spec 7.3: origin at the centre of the chip top surface, +Z toward the lid, mm",
            "cell": {
                "x_min_mm": self.x_min_mm,
                "x_max_mm": self.x_max_mm,
                "y_min_mm": self.y_min_mm,
                "y_max_mm": self.y_max_mm,
                "z_substrate_bottom_mm": self.z_substrate_bottom_mm,
                "z_chip_top_mm": self.z_chip_top_mm,
                "z_lid_mm": self.z_lid_mm,
            },
            "substrate": {
                "z_min_mm": self.z_substrate_bottom_mm,
                "z_max_mm": self.z_chip_top_mm,
                "permittivity": self.substrate_eps_r,
            },
            "conductors": {k: [r.polygon() for r in v] for k, v in self.conductors.items()},
            "etch": [r.polygon() for r in self.etch],
            "ports": {k: [r.polygon() for r in v] for k, v in self.ports.items()},
            "port_directions": {k: list(v) for k, v in self.port_directions.items()},
            "min_gap_mm": self.min_gap_mm,
            "resonator_total_length_mm": self.resonator_total_length_mm,
            "etched_area_mm2": round(self.etched_area_mm2(), PREVIEW_DECIMALS),
            "conductor_area_mm2": round(self.conductor_area_mm2(), PREVIEW_DECIMALS),
            "ground_plane_note": (
                "the ground plane is the whole z = 0 cell top surface minus the union of "
                "the etch polygons; conductors inside etch regions are PEC islands of "
                "their node; the CPW short bar joins the centre conductor to the ground"
            ),
            "notes": list(self.notes),
        }


# --- meander construction ------------------------------------------------------


@dataclass(frozen=True)
class _Segment:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def length(self) -> float:
        return abs(self.x1 - self.x0) + abs(self.y1 - self.y0)

    @property
    def along_x(self) -> bool:
        return abs(self.y1 - self.y0) <= TOL_MM


def _meander_centreline(
    start_x: float,
    start_y: float,
    total_length: float,
    first_straight: float,
    leg: float,
    pitch: float,
    x_range: tuple[float, float],
    y_range: tuple[float, float],
    lateral_halfwidth: float,
) -> list[_Segment]:
    """Deterministic meander centre line of exactly ``total_length``.

    Start at ``(start_x, start_y)``; run +X by ``first_straight``; then legs
    of ``leg`` along Y alternating +Y / -Y between ``start_y - leg/2`` and
    ``start_y + leg/2`` (the first leg is the half leg from ``start_y``),
    joined by +X connectors of ``pitch``. The last segment is truncated so
    that the accumulated length equals ``total_length``. ``lateral_halfwidth``
    is the half width of the widest strip (slot) carried along the line, used
    to test the declared x/y ranges. Raises ``ValueError`` if the meander
    cannot fit.
    """
    if total_length <= 0.0:
        raise ValueError("resonator total length must be positive")
    segments: list[_Segment] = []
    remaining = total_length
    x, y = start_x, start_y

    def emit(dx: float, dy: float) -> None:
        nonlocal x, y, remaining
        seg = _Segment(x, y, x + dx, y + dy)
        segments.append(seg)
        x, y = seg.x1, seg.y1
        remaining -= seg.length

    # First straight along +X (truncated if the whole line is shorter).
    emit(min(first_straight, remaining), 0.0)
    y_top, y_bot = start_y + leg / 2.0, start_y - leg / 2.0
    if y_top + lateral_halfwidth > y_range[1] + TOL_MM or y_bot - lateral_halfwidth < y_range[0] - TOL_MM:
        raise ValueError(f"meander legs of {leg} mm do not fit inside y in {y_range}")
    direction = +1.0
    while remaining > TOL_MM:
        # vertical leg toward y_top (direction +1) or y_bot (direction -1)
        target = y_top if direction > 0 else y_bot
        span = min(abs(target - y), remaining)
        if span > TOL_MM:
            emit(0.0, direction * span)
        if remaining <= TOL_MM:
            break
        # +X connector
        run = min(pitch, remaining)
        if x + run + lateral_halfwidth > x_range[1] + TOL_MM:
            raise ValueError(
                f"meander does not fit: the next leg at x = {x + run:.4f} mm would exceed x in {x_range}"
            )
        emit(run, 0.0)
        direction = -direction
    for seg in segments[1:]:
        for xv in (seg.x0, seg.x1):
            if xv - lateral_halfwidth < x_range[0] - TOL_MM or xv + lateral_halfwidth > x_range[1] + TOL_MM:
                raise ValueError(f"meander leaves x in {x_range} at x = {xv:.4f} mm")
    if abs(remaining) > TOL_MM:
        raise ValueError("meander construction did not consume the declared length")
    return segments


def _strip(seg: _Segment, half: float, ext_start: float, ext_end: float) -> Rect:
    """Rectangle of lateral half-width ``half`` along ``seg``, extended axially."""
    if seg.along_x:
        sgn = 1.0 if seg.x1 >= seg.x0 else -1.0
        xa, xb = seg.x0 - sgn * ext_start, seg.x1 + sgn * ext_end
        return Rect.from_bounds(min(xa, xb), seg.y0 - half, max(xa, xb), seg.y0 + half)
    sgn = 1.0 if seg.y1 >= seg.y0 else -1.0
    ya, yb = seg.y0 - sgn * ext_start, seg.y1 + sgn * ext_end
    return Rect.from_bounds(seg.x0 - half, min(ya, yb), seg.x0 + half, max(ya, yb))


# --- declaration -> ChipCell ---------------------------------------------------


def _feature(decl: dict[str, Any], feature_id: str) -> dict[str, Any]:
    for f in decl["geometry"]["features"]:
        if f["id"] == feature_id:
            return f
    raise ValueError(f"declaration has no geometry feature {feature_id!r}")


def _port(decl: dict[str, Any], port_id: str) -> dict[str, Any]:
    for p in decl["ports"]:
        if p["id"] == port_id:
            return p
    raise ValueError(f"declaration has no port {port_id!r}")


def _material_permittivity(decl: dict[str, Any], material_id: str) -> float:
    for m in decl["materials"]:
        if m["id"] == material_id:
            return float(m["permittivity"])
    raise ValueError(f"declaration has no material {material_id!r}")


def chip_cell_from_declaration(decl: dict[str, Any]) -> ChipCell:
    """Build the S1 :class:`ChipCell` from a parsed coupled-candidate declaration.

    Reads ``geometry.cell``, the features ``F1.island``, ``F1.element_site``,
    ``R1.coupling_pad``, ``R1.cpw`` (with its ``path`` prose, parsed for the
    leg length, pitch and x/y ranges), ``geometry.clearances_mm``, the ports
    ``P_F1`` and ``P_R1`` and the substrate permittivity. The CPW centre line
    starts at the coupling pad's +X edge. ``P_R1`` is placed 0.150 mm before
    the short along the last leg; its directions point from ground into the
    centre conductor and are therefore perpendicular to that leg. When that
    disagrees with the declared directions a note records it (the declaration
    lists ``['+Y', '-Y']``, which presumes a last leg along X).
    """
    cell = decl["geometry"]["cell"]
    island_f = _feature(decl, "F1.island")
    site_f = _feature(decl, "F1.element_site")
    pad_f = _feature(decl, "R1.coupling_pad")
    cpw_f = _feature(decl, "R1.cpw")
    if island_f["shape"] != "rectangle" or pad_f["shape"] != "rectangle" or cpw_f["shape"] != "cpw_meander":
        raise ValueError("unexpected feature shapes in the declaration")

    island = Rect(island_f["centre_mm"][0], island_f["centre_mm"][1], island_f["size_mm"][0], island_f["size_mm"][1])
    island_gap = float(island_f["gap_to_ground_mm"])
    pad = Rect(pad_f["centre_mm"][0], pad_f["centre_mm"][1], pad_f["size_mm"][0], pad_f["size_mm"][1])
    pad_gap_ground = float(pad_f["gap_to_ground_mm"])
    pad_gap_island = float(pad_f["gap_to_island_mm"])
    site = Rect(site_f["centre_mm"][0], site_f["centre_mm"][1], site_f["size_mm"][0], site_f["size_mm"][1])

    w = float(cpw_f["centre_width_mm"])
    g = float(cpw_f["gap_mm"])
    total = float(cpw_f["total_length_mm"])
    m = _PATH_RE.search(cpw_f["path"])
    if m is None:
        raise ValueError(f"cannot parse the R1.cpw path description: {cpw_f['path']!r}")
    leg = float(m["leg"])
    pitch = float(m["pitch"])
    x_range = (float(m["x0"]), float(m["x1"]))
    y_range = (float(m["y0"]), float(m["y1"]))

    segments = _meander_centreline(
        start_x=pad.x_max,
        start_y=pad.cy_mm,
        total_length=total,
        first_straight=MEANDER_FIRST_STRAIGHT_MM,
        leg=leg,
        pitch=pitch,
        x_range=x_range,
        y_range=y_range,
        lateral_halfwidth=w / 2.0 + g,
    )
    n = len(segments)
    cpw_rects: list[Rect] = []
    slot_rects: list[Rect] = []
    for i, seg in enumerate(segments):
        first, last = i == 0, i == n - 1
        cpw_rects.append(_strip(seg, w / 2.0, 0.0 if first else w / 2.0, 0.0 if last else w / 2.0))
        slot_rects.append(_strip(seg, w / 2.0 + g, 0.0 if first else w / 2.0 + g, 0.0 if last else w / 2.0 + g))
    last_seg = segments[-1]
    # The short: a bar spanning both gaps just beyond the centre-line end, so
    # the centre conductor meets the ground galvanically (spec: shorted end).
    if last_seg.along_x:
        sgn = 1.0 if last_seg.x1 >= last_seg.x0 else -1.0
        xa, xb = last_seg.x1, last_seg.x1 + sgn * g
        short_bar = Rect.from_bounds(min(xa, xb), last_seg.y1 - w / 2.0 - g, max(xa, xb), last_seg.y1 + w / 2.0 + g)
    else:
        sgn = 1.0 if last_seg.y1 >= last_seg.y0 else -1.0
        ya, yb = last_seg.y1, last_seg.y1 + sgn * g
        short_bar = Rect.from_bounds(last_seg.x1 - w / 2.0 - g, min(ya, yb), last_seg.x1 + w / 2.0 + g, max(ya, yb))
    cpw_rects.append(short_bar)

    # Ports.
    p_f1 = _port(decl, "P_F1")
    p_f1_rect = Rect(p_f1["centre_mm"][0], p_f1["centre_mm"][1], p_f1["size_mm"][0], p_f1["size_mm"][1])
    if p_f1_rect != site:
        raise ValueError("P_F1 must coincide with F1.element_site")
    p_r1 = _port(decl, "P_R1")
    port_len = float(min(p_r1["size_mm"]))  # extent along the leg (0.020 mm)
    declared_r1_dirs = list(p_r1["direction"])
    back = 0.150  # mm before the short along the last leg (declaration: ports.P_R1.surface)
    if last_seg.length + TOL_MM < back:
        raise ValueError("the last meander leg is shorter than the 0.150 mm port set-back")
    notes: list[str] = []
    if last_seg.along_x:
        sgn = 1.0 if last_seg.x1 >= last_seg.x0 else -1.0
        xc = last_seg.x1 - sgn * back
        yc = last_seg.y1
        r1_rects = [
            Rect(xc, yc - w / 2.0 - g / 2.0, port_len, g),  # gap on the -Y side
            Rect(xc, yc + w / 2.0 + g / 2.0, port_len, g),  # gap on the +Y side
        ]
        r1_dirs = ["+Y", "-Y"]
    else:
        sgn = 1.0 if last_seg.y1 >= last_seg.y0 else -1.0
        yc = last_seg.y1 - sgn * back
        xc = last_seg.x1
        r1_rects = [
            Rect(xc - w / 2.0 - g / 2.0, yc, g, port_len),  # gap on the -X side
            Rect(xc + w / 2.0 + g / 2.0, yc, g, port_len),  # gap on the +X side
        ]
        r1_dirs = ["+X", "-X"]
    if r1_dirs != declared_r1_dirs:
        notes.append(
            f"P_R1 directions realised as {r1_dirs} (from ground into the centre conductor, "
            f"perpendicular to the last meander leg, which runs along "
            f"{'X' if last_seg.along_x else 'Y'}); the declaration lists {declared_r1_dirs}"
        )

    clearances = {k: float(v) for k, v in decl["geometry"].get("clearances_mm", {}).items()}
    return ChipCell(
        x_min_mm=float(cell["x_min_mm"]),
        x_max_mm=float(cell["x_max_mm"]),
        y_min_mm=float(cell["y_min_mm"]),
        y_max_mm=float(cell["y_max_mm"]),
        z_substrate_bottom_mm=float(cell["z_substrate_bottom_mm"]),
        z_chip_top_mm=float(cell["z_chip_top_mm"]),
        z_lid_mm=float(cell["z_lid_mm"]),
        substrate_eps_r=_material_permittivity(decl, "substrate"),
        conductors={"F1.island": [island], "R1.coupling_pad": [pad], "R1.cpw": cpw_rects},
        etch=[island.inflate(island_gap), pad.inflate(pad_gap_ground), *slot_rects],
        ports={"P_F1": [p_f1_rect], "P_R1": r1_rects},
        port_directions={"P_F1": [str(p_f1["direction"])], "P_R1": r1_dirs},
        min_gap_mm=min(island_gap, pad_gap_ground, pad_gap_island, g),
        resonator_total_length_mm=total,
        clearances_mm=clearances,
        declared_gaps_mm={
            "F1.island.gap_to_ground_mm": island_gap,
            "R1.coupling_pad.gap_to_ground_mm": pad_gap_ground,
            "R1.coupling_pad.gap_to_island_mm": pad_gap_island,
            "R1.cpw.gap_mm": g,
        },
        notes=tuple(notes),
    )


def centreline_length_mm(cell: ChipCell) -> float:
    """Centre-line length of the R1 CPW recovered from its conductor rectangles.

    Each segment rectangle is extended by half the centre width at every
    joint (both rectangles cover the corner square), so the centre line is
    the sum of the rectangles' long sides minus those extensions. The short
    bar (last rectangle) carries no length.
    """
    rects = cell.conductors["R1.cpw"][:-1]
    if not rects:
        return 0.0
    w = min(min(r.w_mm, r.h_mm) for r in rects)
    total = 0.0
    n = len(rects)
    for i, r in enumerate(rects):
        long_side = max(r.w_mm, r.h_mm)
        ext = (0.0 if i == 0 else w / 2.0) + (0.0 if i == n - 1 else w / 2.0)
        total += long_side - ext
    return total


__all__ = [
    "MEANDER_FIRST_STRAIGHT_MM",
    "TOL_MM",
    "ChipCell",
    "Rect",
    "centreline_length_mm",
    "chip_cell_from_declaration",
    "union_area_mm2",
]
