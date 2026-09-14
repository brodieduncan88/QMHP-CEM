"""Palace configuration for the Object 001 empty-cavity eigenmode problem.

Builds the JSON document Palace reads. Every number in it is either taken
from the candidate (ENGINEERING-SEED dimensions) or is a declared
ENGINEERING-RULE of this adapter, listed in :data:`SOLVER_RULES` so that the
run record can carry them verbatim.

The Palace configuration schema this targets is the one shipped with the
pinned release in ``docker/palace.Dockerfile`` (``Problem`` / ``Model`` /
``Domains`` / ``Boundaries`` / ``Solver``). Attribute numbers must match the
physical groups written by :mod:`solvers.palace.mesh`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from solvers.palace.analytic import rectangular_cavity_modes

#: Gmsh physical-group tags. Palace addresses regions by these integers.
VACUUM_ATTRIBUTE = 1
PEC_ATTRIBUTE = 2

#: Palace's mesh length unit: the mesh is in mm (spec §7.3), Palace works in
#: metres, so L0 converts.
L0_MM_TO_M = 1.0e-3

#: ENGINEERING-RULE values of this adapter, recorded in every run.
SOLVER_RULES: dict[str, Any] = {
    "finite_element_order": 2,
    "eigenmodes_requested": 4,
    "eigenvalue_tolerance": 1.0e-6,
    "linear_solver_tolerance": 1.0e-8,
    "linear_solver_max_iterations": 400,
    # Shift-and-invert target as a fraction of the analytic fundamental. Placing
    # the target just below the first expected mode makes the eigensolver find
    # the lowest modes first.
    "eigenmode_target_fraction_of_analytic_fundamental": 0.85,
    "characteristic_mesh_length_rule": "min(cavity_height_above_chip, cavity_width / 12)",
    "domain": "empty vacuum cavity of Object 001 as a closed PEC box; chip, "
    "recess step, launches and lid are NOT modelled in this milestone",
}


@dataclass(frozen=True)
class SolverDomain:
    """The box Palace solves, in the frozen frame of spec §7.3 (mm)."""

    x_min_mm: float
    x_max_mm: float
    y_min_mm: float
    y_max_mm: float
    z_min_mm: float
    z_max_mm: float

    @property
    def size_mm(self) -> tuple[float, float, float]:
        return (
            self.x_max_mm - self.x_min_mm,
            self.y_max_mm - self.y_min_mm,
            self.z_max_mm - self.z_min_mm,
        )

    @property
    def characteristic_length_mm(self) -> float:
        a, _, d = self.size_mm
        return min(d, a / 12.0)

    def as_dict(self) -> dict[str, float]:
        return {
            "x_min_mm": self.x_min_mm,
            "x_max_mm": self.x_max_mm,
            "y_min_mm": self.y_min_mm,
            "y_max_mm": self.y_max_mm,
            "z_min_mm": self.z_min_mm,
            "z_max_mm": self.z_max_mm,
        }


def solver_domain(candidate) -> SolverDomain:  # noqa: ANN001
    """Derive the empty-cavity solver domain from a candidate.

    Frame (spec §7.3): origin at the centre of the chip's top surface, +Z
    toward the lid. The vacuum cavity is ``width_mm x height_mm`` in X/Y,
    centred, and extends from the chip top surface (z = 0) up to
    ``height_above_chip_mm``, the underside of the lid.
    """
    cav = candidate.parameters.vacuum_cavity
    return SolverDomain(
        x_min_mm=-cav.width_mm / 2.0,
        x_max_mm=cav.width_mm / 2.0,
        y_min_mm=-cav.height_mm / 2.0,
        y_max_mm=cav.height_mm / 2.0,
        z_min_mm=0.0,
        z_max_mm=cav.height_above_chip_mm,
    )


def analytic_reference(domain: SolverDomain, count: int = 8) -> list[dict[str, Any]]:
    a, b, d = domain.size_mm
    return [
        {"m": mode.m, "n": mode.n, "p": mode.p, "frequency_GHz": mode.frequency_GHz,
         "label": mode.label}
        for mode in rectangular_cavity_modes(a, b, d, count=count)
    ]


def build_config(mesh_filename: str, domain: SolverDomain, output_dir: str = "postpro") -> dict[str, Any]:
    """The Palace configuration document, ready to serialise as JSON."""
    fundamental = analytic_reference(domain, count=1)[0]["frequency_GHz"]
    target_GHz = SOLVER_RULES["eigenmode_target_fraction_of_analytic_fundamental"] * fundamental
    return {
        "Problem": {
            "Type": "Eigenmode",
            "Verbose": 2,
            "Output": output_dir,
        },
        "Model": {
            "Mesh": mesh_filename,
            "L0": L0_MM_TO_M,
            "Refinement": {"UniformLevels": 0},
        },
        "Domains": {
            "Materials": [
                {
                    "Attributes": [VACUUM_ATTRIBUTE],
                    "Permeability": 1.0,
                    "Permittivity": 1.0,
                    "LossTan": 0.0,
                }
            ]
        },
        "Boundaries": {
            "PEC": {"Attributes": [PEC_ATTRIBUTE]},
        },
        "Solver": {
            "Order": SOLVER_RULES["finite_element_order"],
            "Device": "CPU",
            "Eigenmode": {
                "N": SOLVER_RULES["eigenmodes_requested"],
                "Tol": SOLVER_RULES["eigenvalue_tolerance"],
                "Target": round(target_GHz, 6),
                "Save": 0,
            },
            "Linear": {
                "Type": "Default",
                "KSPType": "GMRES",
                "Tol": SOLVER_RULES["linear_solver_tolerance"],
                "MaxIts": SOLVER_RULES["linear_solver_max_iterations"],
            },
        },
    }
