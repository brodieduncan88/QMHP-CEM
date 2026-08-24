"""Candidate contract (spec §3.1).

A Candidate is a typed, validated engineering candidate definition. Its
geometric parameters for Object 001 are ``ENGINEERING-SEED`` values (spec
§7.5) — bootstrap engineering assumptions introduced by QMHP-CEM because the
frozen Master does not define them. They are not validated QMHP hardware
dimensions and must never be described as such.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import Field, model_validator

from contracts.common import Classification, StrictModel

#: Candidate ID format, e.g. QMHP-CEM-A-RF-000001 (spec §8.2).
CANDIDATE_ID_PATTERN = re.compile(r"^QMHP-CEM-[A-Z]-[A-Z]{2}-\d{6}$")

CANDIDATE_SCHEMA = "qmhp-cem.candidate/0.1.0"

#: The single object type implemented in v0.1 (spec §7.4).
OBJECT001 = "object001_single_device_package"

#: Launch counts the Object 001 generator supports (spec §7.4: two opposing
#: SMP-style launches). ENGINEERING-SEED.
SUPPORTED_LAUNCH_COUNTS: frozenset[int] = frozenset({2})


class ChipParams(StrictModel):
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)
    thickness_mm: float = Field(gt=0)


class PackageParams(StrictModel):
    outer_width_mm: float = Field(gt=0)
    outer_height_mm: float = Field(gt=0)
    body_height_mm: float = Field(gt=0)
    floor_thickness_mm: float = Field(gt=0)


class ChipRecessParams(StrictModel):
    xy_clearance_mm: float = Field(gt=0)
    depth_mm: float = Field(gt=0)


class VacuumCavityParams(StrictModel):
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)
    height_above_chip_mm: float = Field(gt=0)


class LidParams(StrictModel):
    thickness_mm: float = Field(gt=0)


class LaunchParams(StrictModel):
    bore_diameter_mm: float = Field(gt=0)
    count: int = Field(gt=0)


class MountingParams(StrictModel):
    hole_count: int = Field(ge=0, default=4)


class CandidateParameters(StrictModel):
    """Object 001 geometric parameter set. All dimensions ENGINEERING-SEED."""

    chip: ChipParams
    package: PackageParams
    chip_recess: ChipRecessParams
    vacuum_cavity: VacuumCavityParams
    lid: LidParams
    launches: LaunchParams
    mounting: MountingParams = Field(default_factory=MountingParams)


class Candidate(StrictModel):
    """A typed engineering candidate (spec §3.1)."""

    schema_: Literal[CANDIDATE_SCHEMA] = Field(alias="schema")
    candidate_id: str
    object_type: Literal[OBJECT001]
    master_revision: str
    classification: Classification
    created_utc: datetime
    parent_candidate_id: str | None = None
    parameters: CandidateParameters

    model_config = StrictModel.model_config | {"populate_by_name": True}

    # --- validation (spec §3.1 "Required validation") ----------------------

    @model_validator(mode="after")
    def _validate(self) -> "Candidate":
        if not CANDIDATE_ID_PATTERN.match(self.candidate_id):
            raise ValueError(
                f"candidate_id {self.candidate_id!r} does not match "
                f"{CANDIDATE_ID_PATTERN.pattern}"
            )
        if self.parent_candidate_id is not None and not CANDIDATE_ID_PATTERN.match(
            self.parent_candidate_id
        ):
            raise ValueError(
                f"parent_candidate_id {self.parent_candidate_id!r} is not a valid ID"
            )

        p = self.parameters
        chip, pkg, recess, cav, lid, launch = (
            p.chip,
            p.package,
            p.chip_recess,
            p.vacuum_cavity,
            p.lid,
            p.launches,
        )

        # Recess must be larger than the chip in X/Y.
        recess_w = chip.width_mm + 2 * recess.xy_clearance_mm
        recess_h = chip.height_mm + 2 * recess.xy_clearance_mm
        if recess_w <= chip.width_mm or recess_h <= chip.height_mm:
            raise ValueError("chip recess must be larger than the chip in X/Y")

        # Recess must fit inside the package.
        if recess_w >= pkg.outer_width_mm or recess_h >= pkg.outer_height_mm:
            raise ValueError(
                f"chip recess ({recess_w:.3f} x {recess_h:.3f} mm) does not fit "
                f"inside package ({pkg.outer_width_mm} x {pkg.outer_height_mm} mm)"
            )

        # Body height must exceed floor thickness.
        if pkg.body_height_mm <= pkg.floor_thickness_mm:
            raise ValueError(
                f"package body_height_mm ({pkg.body_height_mm}) must exceed "
                f"floor_thickness_mm ({pkg.floor_thickness_mm})"
            )

        # Recess must sit within the body above the floor.
        if recess.depth_mm >= pkg.body_height_mm - pkg.floor_thickness_mm:
            raise ValueError(
                "chip recess depth exceeds the available body height above the floor"
            )

        # Recess must actually accommodate the chip in Z.
        if recess.depth_mm < chip.thickness_mm:
            raise ValueError(
                f"chip recess depth ({recess.depth_mm} mm) is shallower than the "
                f"chip ({chip.thickness_mm} mm)"
            )

        # Cavity must leave positive package walls.
        if cav.width_mm >= pkg.outer_width_mm or cav.height_mm >= pkg.outer_height_mm:
            raise ValueError("vacuum cavity leaves no positive package wall in X/Y")
        if cav.width_mm <= recess_w or cav.height_mm <= recess_h:
            raise ValueError("vacuum cavity must enclose the chip recess in X/Y")

        # Launch count must be supported by the object generator.
        if launch.count not in SUPPORTED_LAUNCH_COUNTS:
            raise ValueError(
                f"launch count {launch.count} is not supported by "
                f"{self.object_type}; supported: {sorted(SUPPORTED_LAUNCH_COUNTS)}"
            )

        # Launch bore must fit within the interior height of the package side
        # wall. This check is not required by spec §3.1; it is a CEM structural
        # sanity check (ENGINEERING-RULE) that keeps the generator from being
        # handed a bore taller than the cavity it must open into.
        interior_height_mm = pkg.body_height_mm - pkg.floor_thickness_mm
        if launch.bore_diameter_mm >= interior_height_mm:
            raise ValueError(
                f"launch bore ({launch.bore_diameter_mm} mm) does not fit within "
                f"the package interior height ({interior_height_mm} mm)"
            )

        if lid.thickness_mm <= 0:
            raise ValueError("lid thickness must be positive")

        return self

    # --- helpers ------------------------------------------------------------

    @property
    def recess_width_mm(self) -> float:
        return self.parameters.chip.width_mm + 2 * self.parameters.chip_recess.xy_clearance_mm

    @property
    def recess_height_mm(self) -> float:
        return self.parameters.chip.height_mm + 2 * self.parameters.chip_recess.xy_clearance_mm

    def to_ordered_dict(self) -> dict[str, Any]:
        """Deterministic serialisable form used for hashing (spec §11.4)."""
        return self.model_dump(mode="json", by_alias=True)


def candidate_id(index: int, branch: str = "A", family: str = "RF") -> str:
    """Build a candidate ID, e.g. ``candidate_id(1) -> QMHP-CEM-A-RF-000001``."""
    if index < 1:
        raise ValueError("candidate index is 1-based")
    if index > 999_999:
        raise ValueError("candidate index exceeds the 6-digit ID field")
    return f"QMHP-CEM-{branch}-{family}-{index:06d}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
