"""Gmsh mesh for the Object 001 empty-cavity solver domain.

Produces a tetrahedral mesh of the closed box in :class:`SolverDomain`, with
two physical groups that Palace addresses by attribute number:

* volume ``VACUUM_ATTRIBUTE`` (1): the vacuum interior;
* surface ``PEC_ATTRIBUTE`` (2): every exterior face, perfect conductor.

The file is written as Gmsh MSH 2.2 ASCII, the format the MFEM reader inside
Palace supports most conservatively, and ASCII so that the mesh hash is a
function of geometry and version alone. Gmsh is run single-threaded with
fixed algorithms and an explicit random seed, so the same inputs give the
same mesh with the same gmsh wheel on the same platform; the release is
recorded next to the hash, and a different wheel or platform may legitimately
give a different (equally valid) mesh with a different hash.

gmsh is an optional dependency (``uv sync --extra palace``). When it is
absent this module raises :class:`solvers.adapter.SolverUnavailable`, never a
bare ImportError, so the failure names the remedy.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from solvers.adapter import SolverUnavailable
from solvers.palace.config import PEC_ATTRIBUTE, VACUUM_ATTRIBUTE, SolverDomain

MSH_FORMAT_VERSION = 2.2


@dataclass(frozen=True)
class MeshRecord:
    path: Path
    sha256: str
    gmsh_version: str
    node_count: int
    tetrahedron_count: int
    boundary_triangle_count: int
    characteristic_length_mm: float
    format: str = f"msh{MSH_FORMAT_VERSION}-ascii"

    def as_dict(self) -> dict[str, object]:
        return {
            "file": self.path.name,
            "sha256": self.sha256,
            "gmsh_version": self.gmsh_version,
            "node_count": self.node_count,
            "tetrahedron_count": self.tetrahedron_count,
            "boundary_triangle_count": self.boundary_triangle_count,
            "characteristic_length_mm": self.characteristic_length_mm,
            "format": self.format,
            "physical_groups": {
                "vacuum_volume": VACUUM_ATTRIBUTE,
                "pec_surfaces": PEC_ATTRIBUTE,
            },
        }


def gmsh_available() -> bool:
    try:
        import gmsh  # noqa: F401
    except Exception:  # a broken install is as unusable as an absent one
        return False
    return True


def _require_gmsh():  # noqa: ANN202
    try:
        import gmsh
    except Exception as exc:
        raise SolverUnavailable(
            "palace",
            f"the gmsh Python package is not importable ({exc.__class__.__name__}: {exc})",
            "Install the palace extra: uv sync --extra palace. On Linux gmsh also "
            "needs libGLU (apt-get install libglu1-mesa) even when used headless.",
        ) from exc
    return gmsh


def generate_box_mesh(domain: SolverDomain, output_path: Path) -> MeshRecord:
    """Mesh the solver domain and write it to ``output_path``."""
    gmsh = _require_gmsh()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lc = domain.characteristic_length_mm

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("General.NumThreads", 1)
        gmsh.option.setNumber("Mesh.MaxNumThreads1D", 1)
        gmsh.option.setNumber("Mesh.MaxNumThreads2D", 1)
        gmsh.option.setNumber("Mesh.MaxNumThreads3D", 1)
        gmsh.option.setNumber("Mesh.Algorithm", 6)      # Frontal-Delaunay (2D)
        gmsh.option.setNumber("Mesh.Algorithm3D", 1)    # Delaunay (3D)
        gmsh.option.setNumber("Mesh.RandomSeed", 1)     # gmsh's default, pinned explicitly
        gmsh.option.setNumber("Mesh.Optimize", 1)
        gmsh.option.setNumber("Mesh.OptimizeNetgen", 0)
        gmsh.option.setNumber("Mesh.CharacteristicLengthMin", lc)
        gmsh.option.setNumber("Mesh.CharacteristicLengthMax", lc)
        gmsh.option.setNumber("Mesh.MshFileVersion", MSH_FORMAT_VERSION)
        gmsh.option.setNumber("Mesh.Binary", 0)
        gmsh.option.setNumber("Mesh.SaveAll", 0)

        gmsh.model.add("object001_empty_cavity")
        dx, dy, dz = domain.size_mm
        box = gmsh.model.occ.addBox(domain.x_min_mm, domain.y_min_mm, domain.z_min_mm, dx, dy, dz)
        gmsh.model.occ.synchronize()

        surfaces = [tag for (dim, tag) in gmsh.model.getBoundary([(3, box)], oriented=False)]
        gmsh.model.addPhysicalGroup(3, [box], VACUUM_ATTRIBUTE)
        gmsh.model.setPhysicalName(3, VACUUM_ATTRIBUTE, "vacuum")
        gmsh.model.addPhysicalGroup(2, surfaces, PEC_ATTRIBUTE)
        gmsh.model.setPhysicalName(2, PEC_ATTRIBUTE, "pec")

        gmsh.model.mesh.generate(3)

        node_tags, _, _ = gmsh.model.mesh.getNodes()
        tet_types, tet_tags, _ = gmsh.model.mesh.getElements(3)
        tri_types, tri_tags, _ = gmsh.model.mesh.getElements(2)
        n_tet = sum(len(t) for t in tet_tags)
        n_tri = sum(len(t) for t in tri_tags)
        if n_tet == 0:
            raise RuntimeError("gmsh produced no tetrahedra for the solver domain")

        gmsh.write(str(output_path))
        version = gmsh.option.getString("General.Version")
    finally:
        gmsh.finalize()

    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    return MeshRecord(
        path=output_path,
        sha256=digest,
        gmsh_version=version,
        node_count=len(node_tags),
        tetrahedron_count=n_tet,
        boundary_triangle_count=n_tri,
        characteristic_length_mm=lc,
    )
