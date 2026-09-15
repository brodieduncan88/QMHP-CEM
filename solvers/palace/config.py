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

from solvers.palace.analytic import (
    expected_solver_modes,
    rectangular_cavity_modes,
    rectangular_cavity_modes_below,
)

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
    # Solver.Eigenmode.Tol: Palace's own stopping criterion (SLEPc relative
    # residual on the shift-inverted problem). A mode's presence in eig.csv is
    # Palace's statement that it converged.
    "eigenvalue_tolerance": 1.0e-6,
    # Adapter check on top of Palace's: the a-posteriori backward error Palace
    # writes per mode must not exceed this. Palace's reference cavity example
    # shows backward errors ~100x below Tol, so this rarely binds; it is an
    # ENGINEERING-RULE of QMHP-CEM, not Palace's criterion.
    "eigenmode_backward_error_max_tolerance": 1.0e-6,
    "linear_solver_tolerance": 1.0e-8,
    "linear_solver_max_iterations": 400,
    # Shift-and-invert target as a fraction of the closed-form fundamental of
    # the EMPTY box. The target must lie strictly below the lowest physical
    # mode of the domain actually solved; once a dielectric is added the
    # fundamental drops and this rule must be revisited (a target above the
    # fundamental would skip it silently).
    "eigenmode_target_fraction_of_analytic_fundamental": 0.85,
    # In-plane resolution only. Every requested mode of the empty box is
    # TM_mn0, independent of the cavity height, so the mesh size is tied to the
    # in-plane wavelength rather than to the height; this keeps the mesh
    # identical across a height sweep instead of confounding it.
    "characteristic_mesh_length_rule": "min(cavity_width, cavity_height) / 12",
    # What a first run on this mesh at this order should show against the
    # closed form. Larger deviations are reported as a warning; the hard
    # proof gate below is deliberately loose.
    "expected_relative_deviation": 1.0e-4,
    "domain": "empty vacuum cavity of Object 001 as a closed PEC box; chip, "
    "recess step, launches and lid are NOT modelled in this milestone. All "
    "requested modes are TM_mn0: independent of height_above_chip_mm, so the "
    "closed-form check verifies the X/Y extent and unit scaling, not the height.",
}

#: Hard proof gate for the golden run: |f_palace - f_exact| / f_exact must be
#: below this or the harness exits 4. Loose on purpose (it catches a wrong
#: box, a wrong L0 or a wrong permittivity, not a sub-optimal mesh); the
#: expected deviation is SOLVER_RULES["expected_relative_deviation"].
GOLDEN_RELATIVE_TOLERANCE = 0.02


@dataclass(frozen=True)
class SolverDomain:
    """The box Palace solves, in the frozen frame of spec §7.3 (mm)."""

    x_min_mm: float
    x_max_mm: float
    y_min_mm: float
    y_max_mm: float
    z_min_mm: float
    z_max_mm: float
    #: Explicit mesh characteristic length. ``None`` (the golden default)
    #: applies the in-plane rule ``min(a, b) / 12``; a verification campaign
    #: sets it per run.
    mesh_length_mm: float | None = None

    @property
    def size_mm(self) -> tuple[float, float, float]:
        return (
            self.x_max_mm - self.x_min_mm,
            self.y_max_mm - self.y_min_mm,
            self.z_max_mm - self.z_min_mm,
        )

    @property
    def default_characteristic_length_mm(self) -> float:
        a, b, _ = self.size_mm
        return min(a, b) / 12.0

    @property
    def characteristic_length_mm(self) -> float:
        if self.mesh_length_mm is not None:
            if self.mesh_length_mm <= 0:
                raise ValueError("mesh_length_mm must be positive")
            return float(self.mesh_length_mm)
        return self.default_characteristic_length_mm

    def as_dict(self) -> dict[str, float]:
        out = {
            "x_min_mm": self.x_min_mm,
            "x_max_mm": self.x_max_mm,
            "y_min_mm": self.y_min_mm,
            "y_max_mm": self.y_max_mm,
            "z_min_mm": self.z_min_mm,
            "z_max_mm": self.z_max_mm,
        }
        if self.mesh_length_mm is not None:
            out["mesh_length_mm"] = float(self.mesh_length_mm)
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SolverDomain":
        return cls(
            x_min_mm=float(data["x_min_mm"]),
            x_max_mm=float(data["x_max_mm"]),
            y_min_mm=float(data["y_min_mm"]),
            y_max_mm=float(data["y_max_mm"]),
            z_min_mm=float(data["z_min_mm"]),
            z_max_mm=float(data["z_max_mm"]),
            mesh_length_mm=(float(data["mesh_length_mm"]) if data.get("mesh_length_mm") is not None else None),
        )

    def probe_points_mm(self, fractions: list[tuple[float, float, float]]) -> list[list[float]]:
        """Absolute probe coordinates from fractional positions inside the box."""
        a, b, d = self.size_mm
        return [
            [self.x_min_mm + fx * a, self.y_min_mm + fy * b, self.z_min_mm + fz * d]
            for fx, fy, fz in fractions
        ]


def solver_domain(candidate) -> SolverDomain:  # noqa: ANN001
    """Derive the empty-cavity solver domain from a candidate.

    Frame (spec §7.3): origin at the centre of the chip's top surface, +Z
    toward the lid. The vacuum cavity is ``width_mm x height_mm`` in X/Y,
    centred, and extends from the chip top surface (z = 0) up to
    ``height_above_chip_mm``, the underside of the lid. The package floor
    around the recess sits 0.02 mm above that datum (recess depth minus chip
    thickness); the empty-box abstraction ignores it, and no requested mode
    depends on the height in any case.
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


def _mode_dict(mode) -> dict[str, Any]:  # noqa: ANN001 - CavityMode
    return {"m": mode.m, "n": mode.n, "p": mode.p, "frequency_GHz": mode.frequency_GHz,
            "multiplicity": mode.multiplicity, "label": mode.label}


def analytic_reference(domain: SolverDomain, count: int = 8) -> list[dict[str, Any]]:
    """Distinct closed-form modes of the domain, each with its multiplicity."""
    a, b, d = domain.size_mm
    return [_mode_dict(mode) for mode in rectangular_cavity_modes(a, b, d, count=count)]


def analytic_reference_below(domain: SolverDomain, f_max_GHz: float) -> list[dict[str, Any]]:
    """Every distinct closed-form mode at or below ``f_max_GHz`` (complete)."""
    a, b, d = domain.size_mm
    return [_mode_dict(mode) for mode in rectangular_cavity_modes_below(a, b, d, f_max_GHz)]


def expected_solver_modes_GHz(
    domain: SolverDomain, n_modes: int | None = None, target_GHz: float | None = None
) -> list[float]:
    """What the solver should report for its N modes, repeats included.

    Without a target: the N lowest modes (the golden case). With one: the N
    lowest modes at or above it, which is what Palace's shift-and-invert
    returns for that target.
    """
    a, b, d = domain.size_mm
    n = n_modes or int(SOLVER_RULES["eigenmodes_requested"])
    return expected_solver_modes(a, b, d, n, f_min_GHz=target_GHz)


def default_target_GHz(domain: SolverDomain) -> float:
    fundamental = analytic_reference(domain, count=1)[0]["frequency_GHz"]
    return SOLVER_RULES["eigenmode_target_fraction_of_analytic_fundamental"] * fundamental


def build_config(
    mesh_filename: str,
    domain: SolverDomain,
    output_dir: str = "postpro",
    *,
    eigenmodes: int | None = None,
    target_GHz: float | None = None,
    probes_mm: list[list[float]] | None = None,
) -> dict[str, Any]:
    """The Palace configuration document, ready to serialise as JSON.

    The keyword overrides exist for verification campaigns; left at ``None``
    they reproduce the golden document exactly. ``probes_mm`` adds field
    probes (``Domains.Postprocessing.Probe``) at points given in mesh units;
    Palace then writes ``probe-E.csv`` beside ``eig.csv``.
    """
    n_modes = int(eigenmodes) if eigenmodes is not None else SOLVER_RULES["eigenmodes_requested"]
    if n_modes < 1:
        raise ValueError("eigenmodes must be >= 1")
    target = float(target_GHz) if target_GHz is not None else default_target_GHz(domain)
    if target <= 0:
        raise ValueError("target_GHz must be positive")
    domains: dict[str, Any] = {
        "Materials": [
            {
                "Attributes": [VACUUM_ATTRIBUTE],
                "Permeability": 1.0,
                "Permittivity": 1.0,
                "LossTan": 0.0,
            }
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
        "Domains": domains,
        "Boundaries": {
            "PEC": {"Attributes": [PEC_ATTRIBUTE]},
        },
        "Solver": {
            "Order": SOLVER_RULES["finite_element_order"],
            "Device": "CPU",
            "Eigenmode": {
                "N": n_modes,
                "Tol": SOLVER_RULES["eigenvalue_tolerance"],
                "Target": round(target, 6),
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
