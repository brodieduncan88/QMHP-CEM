"""Palace configuration for the coupled chip-cell eigenmode problem.

Builds the JSON document Palace reads for a **Route A style** eigenmode solve
of the S1 chip cell: vacuum and substrate volumes, PEC on the outer walls and
on the zero-thickness metal sheets, and one lumped **inductive** port at the
fluxonium element site so that Palace writes the energy participation
(``port-EPR.csv``) the route needs.

This module is additive. It does not touch :mod:`solvers.palace.config`,
whose ``build_config`` and ``SOLVER_RULES`` remain the byte-identical golden
path for the empty Object 001 box. Attribute numbers here must match the
physical groups written by :mod:`solvers.palace.coupled_mesh`.

Scope: the numerical-method pilot approved for the checkpoint-A review runs
exactly this problem. **It performs no coupling extraction**: it produces a
mode list, the site participation, and timing. Turning those into a coupling
is Route A's inversion, which is not run here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from solvers.palace.coupled_mesh import TAGS

#: Palace's mesh length unit: the mesh is in mm (spec §7.3), Palace works in
#: metres, so L0 converts. Same value as the golden path.
L0_MM_TO_M = 1.0e-3

#: Physical constants (CODATA exact SI).
ELEMENTARY_CHARGE_C = 1.602176634e-19
PLANCK_J_S = 6.62607015e-34
REDUCED_FLUX_QUANTUM_WB = PLANCK_J_S / (2.0 * ELEMENTARY_CHARGE_C) / (2.0 * math.pi)

#: ENGINEERING-RULE values of the coupled eigenmode solve. Recorded verbatim
#: in every pilot run record. None of these is a physical QMHP requirement.
COUPLED_SOLVER_RULES: dict[str, Any] = {
    # The decision-relevant window of numerical-plan.md §1. The target sits at
    # its floor: Palace returns eigenvalues close to but not below the target,
    # so a target at the floor sweeps the window upward.
    "band_floor_GHz": 0.5,
    "band_ceiling_GHz": 9.0,
    "eigenmode_target_GHz": 0.5,
    # Enough modes to cover the window: the cell's own electromagnetic cavity
    # modes lie far above it (c/2a = 37.5 GHz in vacuum for a 4 mm cell), so
    # the in-band modes are the circuit modes created by the lumped inductor
    # and the distributed resonator. Six leaves margin for a hidden mode.
    "eigenmodes_requested": 6,
    "eigenvalue_tolerance": 1.0e-6,
    "eigenmode_backward_error_max_tolerance": 1.0e-6,
    "linear_solver_tolerance": 1.0e-8,
    "linear_solver_max_iterations": 400,
    "mesh_size_rule": "min_gap/2 at conductor and etch edges, min(cell_x, cell_y)/12 beyond the halo",
    "model": (
        "S1 bounded chip cell: vacuum and substrate volumes, zero-thickness PEC sheets for the "
        "ground plane and conductors, PEC outer walls, one lumped inductive port at the F1 "
        "element site carrying the declared superinductor. The readout tap surfaces carry no "
        "boundary condition in Route A. This is NOT the empty Object 001 box of the golden path."
    ),
}


def superinductor_henry(E_L_GHz: float) -> float:
    """``L = (Phi_0/2pi)^2 / (h E_L)`` in henry for an inductive energy in GHz."""
    if E_L_GHz <= 0:
        raise ValueError("E_L must be positive")
    return REDUCED_FLUX_QUANTUM_WB**2 / (PLANCK_J_S * E_L_GHz * 1e9)


@dataclass(frozen=True)
class CoupledRun:
    """One pilot solve: the two knobs under test plus its identity."""

    name: str
    finite_element_order: int
    halo_mm: float
    level: int = 1
    purpose: str = ""

    def __post_init__(self) -> None:
        if self.finite_element_order not in (1, 2):
            raise ValueError("finite_element_order must be 1 or 2")
        if self.halo_mm <= 0:
            raise ValueError("halo_mm must be positive")
        if self.level < 1:
            raise ValueError("level must be >= 1")

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "finite_element_order": self.finite_element_order,
            "halo_mm": self.halo_mm,
            "level": self.level,
            "purpose": self.purpose,
        }


def build_coupled_config(
    mesh_filename: str,
    *,
    order: int,
    substrate_permittivity: float,
    port_inductance_H: float,
    port_direction: str = "+Y",
    output_dir: str = "postpro",
    eigenmodes: int | None = None,
    target_GHz: float | None = None,
    probes_mm: list[list[float]] | None = None,
) -> dict[str, Any]:
    """The Palace configuration document for the coupled chip cell.

    ``port_inductance_H`` is the declared linear inductance of the fluxonium
    element site: the superinductor alone. The small junction is never a
    linear element (``coupling-definition.md`` §8), and the port is what makes
    Palace report the energy participation.
    """
    if order not in (1, 2):
        raise ValueError("order must be 1 or 2")
    if substrate_permittivity <= 0:
        raise ValueError("substrate permittivity must be positive")
    if port_inductance_H <= 0:
        raise ValueError("the port inductance must be positive")
    n_modes = int(eigenmodes) if eigenmodes is not None else COUPLED_SOLVER_RULES["eigenmodes_requested"]
    if n_modes < 1:
        raise ValueError("eigenmodes must be >= 1")
    target = float(target_GHz) if target_GHz is not None else COUPLED_SOLVER_RULES["eigenmode_target_GHz"]
    if target <= 0:
        raise ValueError("target_GHz must be positive")

    domains: dict[str, Any] = {
        "Materials": [
            {
                "Attributes": [TAGS["vacuum"]],
                "Permeability": 1.0,
                "Permittivity": 1.0,
                "LossTan": 0.0,
            },
            {
                "Attributes": [TAGS["substrate"]],
                "Permeability": 1.0,
                "Permittivity": float(substrate_permittivity),
                "LossTan": 0.0,
            },
        ]
    }
    if probes_mm:
        domains["Postprocessing"] = {
            "Probe": [
                {"Index": i + 1, "Center": [float(c) for c in centre]}
                for i, centre in enumerate(probes_mm)
            ]
        }

    return {
        "Problem": {"Type": "Eigenmode", "Verbose": 2, "Output": output_dir},
        "Model": {
            "Mesh": mesh_filename,
            "L0": L0_MM_TO_M,
            "Refinement": {"UniformLevels": 0},
        },
        "Domains": domains,
        "Boundaries": {
            # Outer walls and every zero-thickness metal sheet.
            "PEC": {"Attributes": [TAGS["outer_pec"], TAGS["sheet_pec"]]},
            # The fluxonium element site. Inductive, so Palace writes
            # port-EPR.csv; not excited, because this is an eigenmode solve.
            "LumpedPort": [
                {
                    "Index": 1,
                    "Attributes": [TAGS["port_F1"]],
                    "Direction": port_direction,
                    "L": float(port_inductance_H),
                }
            ],
        },
        "Solver": {
            "Order": int(order),
            "Device": "CPU",
            "Eigenmode": {
                "N": n_modes,
                "Tol": COUPLED_SOLVER_RULES["eigenvalue_tolerance"],
                "Target": round(target, 6),
                "Save": 0,
            },
            "Linear": {
                "Type": "Default",
                "KSPType": "GMRES",
                "Tol": COUPLED_SOLVER_RULES["linear_solver_tolerance"],
                "MaxIts": COUPLED_SOLVER_RULES["linear_solver_max_iterations"],
            },
        },
    }


__all__ = [
    "COUPLED_SOLVER_RULES",
    "CoupledRun",
    "L0_MM_TO_M",
    "build_coupled_config",
    "superinductor_henry",
]
