"""Mode admission and cross-run mode matching for Palace eigenmode records.

A Palace eigenmode solve returns every eigenpair its solver converged on. That
set is **not** the set of physical resonances of the stated problem: the
requested mode count is filled from whatever the algebra produced, and a mode
can be converged in the linear-algebra sense while not being a resonance of the
operator at all. This module keeps those two questions apart and answers them
in a fixed order:

1. **Join by mode id.** Palace writes five per-mode tables. They are joined on
   the ``m`` column, never by row position, and the join fails loudly if the
   tables disagree about which modes exist.
2. **Row correspondence.** Two physical identities that span the tables are
   checked rather than assumed: the lumped-port relation ``V = i*omega*L*I``
   ties ``eig``, ``port-I`` and ``port-V``; the participation definition
   ``|p_j| = E_ind/(E_elec + E_cap)`` ties ``port-EPR`` to ``domain-E``. A
   positional join that had slipped would break both.
3. **Algebraic convergence.** The backward error against the solver's existing
   tolerance. This certifies the eigenpair, not its physics.
4. **Mode validity.** Whether the mode's reported energies balance. For an
   exact eigenpair of ``K x = w^2 M x`` the two sides are equal by algebra, not
   by approximation, and this is a property of the eigenpair rather than of the
   mesh. A large defect says the reported participation of that row rests on a
   quantity that does not hold together; it does **not**, by itself, say what
   the row is. See ``ADMISSION_RULE["what_it_does_not_establish"]``.
5. **Matching.** Two runs are put in correspondence by two orderings that must
   agree, with a separation guard that is what actually carries the pairing.
   When they do not agree, or the runs admit different numbers of modes, this
   module **refuses to report a comparison** rather than pairing something
   arbitrary. See ``MATCHING_RULE`` for what the ordering check can and cannot
   establish — it is weaker than it looks.

Nothing here extracts a coupling. It produces no ``g``, no charging energy and
no circuit parameter; it decides which rows of a solver record may be compared
with which, and on what evidence.

Deliberately absent: any rule that selects a mode by participation rank alone
(smallest or largest ``|p|``), and any hard-coded mode index. The high
frequency rows of the pilot record carry participations of 1e-7 to 1e-11
*because* their reported energies do not balance, so "smallest ``|p|``"
selects exactly the rows whose participation is least trustworthy, in
preference to the mode it was meant to find.

One unit note, because the column headers are misleading: the four
``domain-E.csv`` columns are headed ``(J)`` but carry **1e9 times** the SI
value. Palace's energy dimensionalisation collapses to the characteristic
time, which it stores in nanoseconds. Every quantity this module uses is a
ratio of two such columns, so the scale cancels; it matters only if a raw
column is ever read as a joule.
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from solvers.palace.outputs import (
    PalaceOutputError,
    parse_domain_energy_csv,
    parse_eig_csv,
    parse_port_epr_csv,
    parse_port_phasor_csv,
)

# --- the rules, stated before they are applied ------------------------------

#: Admission rule for whether a computed mode is a resonance of the stated
#: problem. NEW in the corrective analysis of COUPLED-PILOT-20260916T035733Z.
#:
#: Status: **retrospective** for that record (the record's own numbers were
#: produced before the rule existed and are re-read, never re-run, under it)
#: and **prospective** for the next confirmatory run, where it is declared in
#: advance. It replaces no existing tolerance: the halo criteria
#: (``dp <= 1e-2``, ``df <= 1e-4``) and the backward-error tolerance
#: (``1e-6``) are untouched.
ADMISSION_RULE: dict[str, Any] = {
    "id": "qmhp-cem.mode-admission/0.1.0",
    "quantity": "R = (E_mag + E_ind) / (E_elec + E_cap), from domain-E.csv",
    "admit_when": "abs(R - 1) <= 1e-3",
    "max_energy_balance_defect": 1.0e-3,
    "why_this_quantity": (
        "For an exact eigenpair of the discrete generalised problem K x = w^2 M x, "
        "x^H K x = w^2 x^H M x holds identically, so the magnetic-side and electric-side "
        "energies are equal by algebra rather than by approximation. Palace normalises each "
        "converged eigenvector against Re(M) — the real-permittivity mass plus any lumped-port "
        "capacitance — which is why E_elec is a per-run constant here (no port capacitance, no "
        "loss tangent). R is dimensionless, needs no mesh, no second run and no reference "
        "frequency, and is computed from a file the solver already writes."
    ),
    "what_it_establishes": (
        "That the mode's REPORTED energies balance. Palace's E_ind is not the port stiffness "
        "quadratic form but the rank-one surrogate |V|^2 / (2 w^2 L) built from the port's "
        "line-average voltage, which by Cauchy-Schwarz is a lower bound on it. A row failing "
        "this check is therefore either not an eigenvector at its reported frequency, or an "
        "eigenvector whose stiffness sits in a strongly non-uniform tangential field on the "
        "port that the line average grossly understates. The admission rule does not "
        "distinguish those, and does not need to: the participation p = E_ind/(E_elec + E_cap) "
        "is built from the SAME surrogate, so in either case the reported p for that row is not "
        "a quantity two solves may be compared on."
    ),
    "what_it_does_not_establish": (
        "It does not prove a rejected row is a spurious or null-space mode, and it asserts no "
        "mechanism. Establishing the cause needs the per-mode port stiffness energy "
        "integral(1/Ls * |E_t|^2) over the port surface, which Palace does not write, or the "
        "saved mode fields, which this record does not contain."
    ),
    "why_this_threshold": (
        "Chosen for separation, not for a physical target: it sits far from both observed "
        "populations rather than between two close ones. It is not a physical QMHP threshold "
        "and gates no coupling."
    ),
    "not_used": (
        "participation rank (smallest or largest |p|), mode index, and frequency order "
        "are all excluded from admission"
    ),
    "status": "retrospective for COUPLED-PILOT-20260916T035733Z; prospective for the next confirmatory run",
}

#: Tolerances for the two row-correspondence identities. These check that the
#: five tables describe the same modes; they are not physics thresholds.
ROW_CORRESPONDENCE_TOLERANCE: dict[str, float] = {
    "max_participation_energy_mismatch": 1.0e-6,
    "max_port_impedance_mismatch": 1.0e-6,
}

#: Matching rule between two runs. Also retrospective here, prospective next.
MATCHING_RULE: dict[str, Any] = {
    "id": "qmhp-cem.mode-matching/0.1.1",
    "pairing": (
        "two one-to-one pairings over the admitted in-window modes — by ascending frequency, "
        "and by descending |p| — which must induce the SAME pairing"
    ),
    "what_the_ordering_check_can_and_cannot_do": (
        "Each pairing is formed by sorting the two runs SEPARATELY and zipping, so whenever |p| "
        "is co-monotone with frequency inside each run the two pairings agree BY CONSTRUCTION, "
        "whatever the true correspondence is. The check therefore detects a run whose |p| order "
        "inverts against its frequency order; it is NOT independent evidence that the "
        "correspondence between the runs is right. On COUPLED-PILOT-20260916T035733Z all three "
        "runs are co-monotone, so the check could not have contradicted the frequency pairing "
        "there. The separation guard is what carries the correspondence."
    ),
    "separation_guard": (
        "each pair's frequency shift between runs must be below half the smallest "
        "adjacent-mode spacing in either run, so no swap is possible"
    ),
    "separation_guard_is_vacuous_when": (
        "either run admits a single in-window mode: the adjacent-mode spacing is then infinite, "
        "so the guard cannot fail and the ordering check cannot fail either. Such a match is "
        "reported with guard='VACUOUS' rather than silently as if it had been guarded."
    ),
    "adjacent_gap_is_over_admitted_modes_only": (
        "a rejected row lying between two admitted ones does not narrow the guard; on this "
        "record every rejected row sits above both admitted in-window modes, so it does not bite"
    ),
    "refuses_when": (
        "the two runs admit different numbers of in-window modes, the two pairings "
        "disagree, or the separation guard fails — in each case no comparison is reported"
    ),
    "status": "retrospective for COUPLED-PILOT-20260916T035733Z; prospective for the next confirmatory run",
}

#: Comparison convention. The magnitude convention is the corrective change:
#: the participation carries Palace's ``sign(Re I)``, and the sign of a single
#: port phasor is not invariant under the eigenvector's arbitrary global phase,
#: so a signed difference between two independent solves mixes a convention
#: into a numerical comparison. The *tolerances* are unchanged.
COMPARISON_CONVENTION: dict[str, str] = {
    "delta_f": "|f_a - f_b| / f_a, run A the reference (unchanged)",
    "delta_p": (
        "abs(|p_a| - |p_b|) / max(|p_a|, |p_b|) — MAGNITUDES. Corrective change from the "
        "signed numerator |p_a - p_b|, which is not invariant under the eigenvector phase. "
        "The denominator and the 1e-2 tolerance are unchanged."
    ),
    "signs_preserved": (
        "the signed participation and the complex port current are carried through "
        "unchanged in every record; only the comparison uses magnitudes"
    ),
}


class ModeTableMismatch(PalaceOutputError):
    """The five per-mode tables of one solve disagree about which modes exist."""


class RowCorrespondenceFailure(PalaceOutputError):
    """A physical identity spanning the per-mode tables does not hold."""


# --- one mode, joined across the five tables --------------------------------


@dataclass(frozen=True)
class ModeRecord:
    """One mode of one solve, joined **by mode id** across Palace's tables."""

    mode: int
    frequency_GHz: float
    frequency_im_GHz: float
    backward_error: float
    absolute_error: float | None
    electric_J: float
    magnetic_J: float
    capacitive_J: float
    inductive_J: float
    participation: dict[int, float]
    current_A: dict[int, complex]
    voltage_V: dict[int, complex]

    @property
    def electric_side_J(self) -> float:
        return self.electric_J + self.capacitive_J

    @property
    def magnetic_side_J(self) -> float:
        return self.magnetic_J + self.inductive_J

    @property
    def energy_balance_ratio(self) -> float:
        """``R = (E_mag + E_ind) / (E_elec + E_cap)``; 1 for a resonance."""
        if self.electric_side_J <= 0:
            return math.inf
        return self.magnetic_side_J / self.electric_side_J

    @property
    def energy_balance_defect(self) -> float:
        """``|R - 1|``. The admission quantity."""
        ratio = self.energy_balance_ratio
        return math.inf if math.isinf(ratio) else abs(ratio - 1.0)

    @property
    def lumped_magnetic_fraction(self) -> float:
        """``E_ind / (E_mag + E_ind)``: how much of the magnetic side is lumped.

        A **descriptive** label only. It never enters admission or matching.
        """
        total = self.magnetic_side_J
        return self.inductive_J / total if total > 0 else math.nan

    def abs_participation(self, port: int = 1) -> float:
        return abs(self.participation.get(port, 0.0))

    def surrogate_relative_bound(self, port: int = 1) -> float:
        """How much of this row's own ``|p|`` the energy defect could account for.

        With no port capacitance and an exact ``E_mag``, equipartition gives the
        port's true participation as ``p_true = p + (1 - R)`` exactly, so
        ``(1 - R)/|p|`` bounds the *relative* error the rank-one surrogate could
        be making on this row's participation.

        This matters because admission bounds the **absolute** defect while the
        comparison tolerance is **relative**: a row can be admitted and still
        carry a relative correction larger than the tolerance it is about to be
        compared under. On the pilot record P2's admitted mode 9 does exactly
        that (``1.47e-2`` against a ``1e-2`` tolerance), while both matched
        in-window pairs sit near ``1.2e-3``.
        """
        magnitude = self.abs_participation(port)
        if magnitude <= 0:
            return math.inf
        return self.energy_balance_defect / magnitude

    def signed_participation(self, port: int = 1) -> float:
        return self.participation.get(port, 0.0)

    def current_phase_deg(self, port: int = 1) -> float:
        """``arg(I)`` in degrees.

        Recorded for completeness. It is **not** comparable between solves: an
        eigenvector is defined up to a global complex scale, so this rotates
        freely. Phase-invariant combinations (magnitudes, and ratios of two
        phasors of the same mode such as ``V/I``) are the comparable ones.
        """
        value = self.current_A.get(port)
        return math.degrees(cmath.phase(value)) if value is not None else math.nan

    def in_window(self, floor_GHz: float, ceiling_GHz: float) -> bool:
        return floor_GHz <= self.frequency_GHz <= ceiling_GHz

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "frequency_GHz": self.frequency_GHz,
            "frequency_im_GHz": self.frequency_im_GHz,
            "backward_error": self.backward_error,
            "absolute_error": self.absolute_error,
            "energy_J": {
                "E_elec": self.electric_J,
                "E_mag": self.magnetic_J,
                "E_cap": self.capacitive_J,
                "E_ind": self.inductive_J,
            },
            "energy_balance_ratio": self.energy_balance_ratio,
            "energy_balance_defect": self.energy_balance_defect,
            "lumped_magnetic_fraction": self.lumped_magnetic_fraction,
            "participation_signed": dict(sorted(self.participation.items())),
            "participation_abs": {j: abs(p) for j, p in sorted(self.participation.items())},
            "surrogate_relative_bound": {
                j: self.surrogate_relative_bound(j) for j in sorted(self.participation)
            },
            "current_A": {
                j: {"re": v.real, "im": v.imag, "abs": abs(v)}
                for j, v in sorted(self.current_A.items())
            },
            "voltage_V": {
                j: {"re": v.real, "im": v.imag, "abs": abs(v)}
                for j, v in sorted(self.voltage_V.items())
            },
            "current_phase_deg": {j: self.current_phase_deg(j) for j in sorted(self.current_A)},
        }


def join_modes_by_id(postpro_dir: Path) -> list[ModeRecord]:
    """Join ``eig``, ``domain-E``, ``port-EPR``, ``port-I`` and ``port-V`` on ``m``.

    Raises :class:`ModeTableMismatch` when the tables do not cover exactly the
    same set of mode ids. Row position is never used.
    """
    postpro = Path(postpro_dir)
    eig = {int(round(r.index)): r for r in parse_eig_csv(postpro / "eig.csv").rows}
    energy = {int(round(r.index)): r for r in parse_domain_energy_csv(postpro / "domain-E.csv")}
    epr = {r.mode: r for r in parse_port_epr_csv(postpro / "port-EPR.csv")}
    current = {r.mode: r for r in parse_port_phasor_csv(postpro / "port-I.csv", "I")}
    voltage = {r.mode: r for r in parse_port_phasor_csv(postpro / "port-V.csv", "V")}

    tables = {
        "eig.csv": set(eig),
        "domain-E.csv": set(energy),
        "port-EPR.csv": set(epr),
        "port-I.csv": set(current),
        "port-V.csv": set(voltage),
    }
    reference = tables["eig.csv"]
    disagreeing = {name: sorted(ids ^ reference) for name, ids in tables.items() if ids != reference}
    if disagreeing:
        raise ModeTableMismatch(
            f"{postpro}: the per-mode tables disagree about which modes exist. "
            f"eig.csv has {sorted(reference)}; symmetric differences: {disagreeing}"
        )

    return [
        ModeRecord(
            mode=m,
            frequency_GHz=eig[m].frequency_re_GHz,
            frequency_im_GHz=eig[m].frequency_im_GHz,
            backward_error=eig[m].backward_error,
            absolute_error=eig[m].absolute_error,
            electric_J=energy[m].electric_J,
            magnetic_J=energy[m].magnetic_J,
            capacitive_J=energy[m].capacitive_J,
            inductive_J=energy[m].inductive_J,
            participation=dict(epr[m].participation),
            current_A=dict(current[m].phasor),
            voltage_V=dict(voltage[m].phasor),
        )
        for m in sorted(reference)
    ]


# --- row correspondence -----------------------------------------------------


@dataclass(frozen=True)
class RowCorrespondenceReport:
    """Whether the joined tables really describe the same modes."""

    modes_checked: int
    max_participation_energy_mismatch: float
    max_port_impedance_mismatch: float
    worst_participation_mode: int | None
    worst_impedance_mode: int | None
    ok: bool
    identities: tuple[str, str] = (
        "|p_j| == E_ind / (E_elec + E_cap)   [port-EPR.csv vs domain-E.csv]",
        "|V_j| == 2*pi*f * L_j * |I_j|       [port-V.csv vs port-I.csv vs eig.csv]",
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "modes_checked": self.modes_checked,
            "identities_checked": list(self.identities),
            "max_participation_energy_mismatch": self.max_participation_energy_mismatch,
            "worst_participation_mode": self.worst_participation_mode,
            "max_port_impedance_mismatch": self.max_port_impedance_mismatch,
            "worst_impedance_mode": self.worst_impedance_mode,
            "tolerance": dict(ROW_CORRESPONDENCE_TOLERANCE),
            "ok": self.ok,
        }


def check_row_correspondence(
    modes: list[ModeRecord],
    port_inductance_H: dict[int, float],
    *,
    tolerance: dict[str, float] | None = None,
    strict: bool = False,
) -> RowCorrespondenceReport:
    """Check two physical identities that span the per-mode tables.

    Both are independent of the join: if ``eig``, ``domain-E`` and the port
    tables had been aligned positionally and slipped, each identity would fail
    by orders of magnitude.
    """
    limits = dict(ROW_CORRESPONDENCE_TOLERANCE)
    if tolerance:
        limits.update(tolerance)

    worst_p, worst_p_mode = 0.0, None
    worst_z, worst_z_mode = 0.0, None
    for record in modes:
        for port, signed in record.participation.items():
            reference = record.inductive_J / record.electric_side_J if record.electric_side_J > 0 else math.inf
            scale = max(abs(signed), abs(reference))
            if scale > 0:
                mismatch = abs(abs(signed) - reference) / scale
                if mismatch > worst_p:
                    worst_p, worst_p_mode = mismatch, record.mode
        for port, inductance in port_inductance_H.items():
            current = record.current_A.get(port)
            voltage = record.voltage_V.get(port)
            if current is None or voltage is None:
                continue
            predicted = 2.0 * math.pi * record.frequency_GHz * 1e9 * inductance * abs(current)
            scale = max(abs(voltage), predicted)
            if scale > 0:
                mismatch = abs(abs(voltage) - predicted) / scale
                if mismatch > worst_z:
                    worst_z, worst_z_mode = mismatch, record.mode

    ok = (
        worst_p <= limits["max_participation_energy_mismatch"]
        and worst_z <= limits["max_port_impedance_mismatch"]
    )
    report = RowCorrespondenceReport(
        modes_checked=len(modes),
        max_participation_energy_mismatch=worst_p,
        max_port_impedance_mismatch=worst_z,
        worst_participation_mode=worst_p_mode,
        worst_impedance_mode=worst_z_mode,
        ok=ok,
    )
    if strict and not ok:
        raise RowCorrespondenceFailure(
            f"row correspondence failed: participation/energy mismatch {worst_p:.3e} "
            f"(mode {worst_p_mode}), port impedance mismatch {worst_z:.3e} (mode {worst_z_mode})"
        )
    return report


# --- admission --------------------------------------------------------------

Disposition = Literal["ADMITTED", "REJECTED_ENERGY_BALANCE", "REJECTED_NOT_CONVERGED"]


@dataclass(frozen=True)
class AdmittedMode:
    record: ModeRecord
    disposition: Disposition
    converged: bool
    balanced: bool

    def as_dict(self) -> dict[str, Any]:
        payload = self.record.as_dict()
        payload.update(
            {
                "disposition": self.disposition,
                "algebraically_converged": self.converged,
                "energy_balanced": self.balanced,
            }
        )
        return payload


@dataclass(frozen=True)
class AdmissionReport:
    """Every computed mode of one solve with its disposition."""

    run: str
    modes: list[AdmittedMode]
    backward_error_tolerance: float
    max_energy_balance_defect: float
    row_correspondence: RowCorrespondenceReport | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def admitted(self) -> list[ModeRecord]:
        return [m.record for m in self.modes if m.disposition == "ADMITTED"]

    @property
    def rejected(self) -> list[AdmittedMode]:
        return [m for m in self.modes if m.disposition != "ADMITTED"]

    def admitted_in_window(self, floor_GHz: float, ceiling_GHz: float) -> list[ModeRecord]:
        return [r for r in self.admitted if r.in_window(floor_GHz, ceiling_GHz)]

    @property
    def separation_decades(self) -> float | None:
        """How far apart the admitted and rejected populations sit in ``|R-1|``.

        ``log10(min rejected defect / max admitted defect)``. A rule whose two
        populations are not separated is a rule that could go either way on the
        next run; this number is what makes the threshold checkable.
        """
        admitted = [m.record.energy_balance_defect for m in self.modes if m.disposition == "ADMITTED"]
        rejected = [
            m.record.energy_balance_defect
            for m in self.modes
            if m.disposition == "REJECTED_ENERGY_BALANCE"
        ]
        if not admitted or not rejected:
            return None
        worst_admitted = max(admitted)
        best_rejected = min(rejected)
        if worst_admitted <= 0 or math.isinf(best_rejected):
            return None
        return math.log10(best_rejected / worst_admitted)

    def as_dict(self) -> dict[str, Any]:
        return {
            "run": self.run,
            "rule": dict(ADMISSION_RULE),
            "backward_error_tolerance": self.backward_error_tolerance,
            "max_energy_balance_defect": self.max_energy_balance_defect,
            "modes_computed": len(self.modes),
            "modes_admitted": len(self.admitted),
            "separation_decades": self.separation_decades,
            "row_correspondence": self.row_correspondence.as_dict() if self.row_correspondence else None,
            "modes": [m.as_dict() for m in self.modes],
            "notes": list(self.notes),
        }


def admit_modes(
    run: str,
    modes: list[ModeRecord],
    *,
    backward_error_tolerance: float,
    max_energy_balance_defect: float | None = None,
    row_correspondence: RowCorrespondenceReport | None = None,
) -> AdmissionReport:
    """Classify every computed mode.

    ``backward_error_tolerance`` is the solver's **existing** tolerance and is
    passed in rather than defined here, so this module cannot loosen it.
    Algebraic convergence and energy balance are separate dispositions: a mode
    can converge perfectly and still not be a resonance.
    """
    limit = (
        ADMISSION_RULE["max_energy_balance_defect"]
        if max_energy_balance_defect is None
        else max_energy_balance_defect
    )
    classified: list[AdmittedMode] = []
    for record in modes:
        converged = record.backward_error <= backward_error_tolerance
        balanced = record.energy_balance_defect <= limit
        if not converged:
            disposition: Disposition = "REJECTED_NOT_CONVERGED"
        elif not balanced:
            disposition = "REJECTED_ENERGY_BALANCE"
        else:
            disposition = "ADMITTED"
        classified.append(
            AdmittedMode(record=record, disposition=disposition, converged=converged, balanced=balanced)
        )
    return AdmissionReport(
        run=run,
        modes=classified,
        backward_error_tolerance=backward_error_tolerance,
        max_energy_balance_defect=limit,
        row_correspondence=row_correspondence,
    )


# --- descriptive roles ------------------------------------------------------

RoleLabel = Literal["LUMPED_DOMINATED", "FIELD_DOMINATED"]


@dataclass(frozen=True)
class RoleAssignment:
    """A descriptive label for an admitted mode, from its energy partition.

    ``LUMPED_DOMINATED`` means most of the mode's magnetic-side energy sits in
    the lumped inductive element at the device site; ``FIELD_DOMINATED`` means
    most of it is in the distributed field. In the S1 cell those correspond to
    the fluxonium-like and readout-like modes respectively.

    **This is not independent evidence.** For a single inductive port,
    ``|p| = E_ind/(E_elec + E_cap)`` and
    ``lumped_magnetic_fraction = E_ind/(E_mag + E_ind)`` differ only by the
    mode's energy-balance defect, so on an *admitted* mode the two orderings
    agree by construction and confirming one with the other proves nothing.
    What makes the label usable is that admission comes first: it is applied
    only to rows that are resonances, where a small participation means a
    weakly participating resonance rather than a row that is not a mode.
    """

    record: ModeRecord
    label: RoleLabel
    lumped_magnetic_fraction: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.record.mode,
            "frequency_GHz": self.record.frequency_GHz,
            "label": self.label,
            "lumped_magnetic_fraction": self.lumped_magnetic_fraction,
            "abs_participation": self.record.abs_participation(),
            "basis": "E_ind / (E_mag + E_ind) from domain-E.csv; descriptive only",
        }


def label_roles(admitted: list[ModeRecord], *, port: int = 1) -> list[RoleAssignment]:
    """Label admitted modes by where their magnetic-side energy sits."""
    labelled: list[RoleAssignment] = []
    for record in admitted:
        fraction = record.lumped_magnetic_fraction
        label: RoleLabel = "LUMPED_DOMINATED" if fraction >= 0.5 else "FIELD_DOMINATED"
        labelled.append(RoleAssignment(record=record, label=label, lumped_magnetic_fraction=fraction))
    return labelled


def unique_field_dominated(admitted: list[ModeRecord], *, port: int = 1) -> ModeRecord | None:
    """The single field-dominated admitted mode, or ``None`` if not unique.

    The frozen halo criterion is written about "the readout-like mode". When
    the admitted set does not contain exactly one field-dominated mode the
    criterion has no unambiguous subject, and ``None`` is returned so the
    caller reports every matched pair instead of choosing one.
    """
    candidates = [r.record for r in label_roles(admitted, port=port) if r.label == "FIELD_DOMINATED"]
    return candidates[0] if len(candidates) == 1 else None


# --- matching ---------------------------------------------------------------

MatchStatus = Literal["MATCHED", "COUNT_MISMATCH", "ORDERING_DISAGREEMENT", "SEPARATION_GUARD", "EMPTY"]


@dataclass(frozen=True)
class MatchedPair:
    a: ModeRecord
    b: ModeRecord
    delta_f_relative: float
    delta_abs_participation_relative: dict[int, float]
    signed_participation: dict[str, dict[int, float]]
    frequency_shift_GHz: float
    separation_limit_GHz: float

    @property
    def separation_margin(self) -> float:
        """How far inside the guard this pair sits. ``inf`` when vacuous."""
        if self.frequency_shift_GHz <= 0:
            return math.inf
        return self.separation_limit_GHz / self.frequency_shift_GHz

    @property
    def guard(self) -> str:
        return "VACUOUS" if math.isinf(self.separation_limit_GHz) else "APPLIED"

    def as_dict(self) -> dict[str, Any]:
        return {
            "a": {"mode": self.a.mode, "frequency_GHz": self.a.frequency_GHz},
            "b": {"mode": self.b.mode, "frequency_GHz": self.b.frequency_GHz},
            "delta_f_relative": self.delta_f_relative,
            "guard": self.guard,
            "separation_margin": self.separation_margin,
            "surrogate_relative_bound": {
                "a": {j: self.a.surrogate_relative_bound(j) for j in sorted(self.a.participation)},
                "b": {j: self.b.surrogate_relative_bound(j) for j in sorted(self.b.participation)},
            },
            "delta_abs_participation_relative": dict(sorted(self.delta_abs_participation_relative.items())),
            "abs_participation": {
                "a": {j: abs(p) for j, p in sorted(self.a.participation.items())},
                "b": {j: abs(p) for j, p in sorted(self.b.participation.items())},
            },
            "signed_participation_preserved": self.signed_participation,
            "frequency_shift_GHz": self.frequency_shift_GHz,
            "separation_limit_GHz": self.separation_limit_GHz,
        }


@dataclass(frozen=True)
class MatchReport:
    status: MatchStatus
    label: str
    pairs: list[MatchedPair]
    reason: str
    a_frequencies_GHz: list[float]
    b_frequencies_GHz: list[float]

    @property
    def comparable(self) -> bool:
        return self.status == "MATCHED" and bool(self.pairs)

    def as_dict(self) -> dict[str, Any]:
        return {
            "comparison": self.label,
            "status": self.status,
            "comparable": self.comparable,
            "reason": self.reason,
            "rule": dict(MATCHING_RULE),
            "convention": dict(COMPARISON_CONVENTION),
            "admitted_in_window_GHz": {"a": self.a_frequencies_GHz, "b": self.b_frequencies_GHz},
            "pairs": [p.as_dict() for p in self.pairs],
        }


def _minimum_adjacent_gap(records: list[ModeRecord]) -> float:
    ordered = sorted(r.frequency_GHz for r in records)
    if len(ordered) < 2:
        return math.inf
    return min(b - a for a, b in zip(ordered, ordered[1:]))


def match_runs(
    label: str,
    a: list[ModeRecord],
    b: list[ModeRecord],
    *,
    port: int = 1,
) -> MatchReport:
    """Put two runs' admitted modes in one-to-one correspondence, or refuse.

    Two independent pairings are formed — by ascending frequency and by
    descending ``|p|`` — and they must agree. Neither is "smallest ``|p|``";
    the participation pairing uses the full ordering of the admitted set, and
    it only ever *confirms* or *contradicts* the frequency pairing.
    """
    freqs_a = [r.frequency_GHz for r in sorted(a, key=lambda r: r.frequency_GHz)]
    freqs_b = [r.frequency_GHz for r in sorted(b, key=lambda r: r.frequency_GHz)]

    if not a or not b:
        return MatchReport("EMPTY", label, [], "one run admitted no mode in the window", freqs_a, freqs_b)

    if len(a) != len(b):
        return MatchReport(
            "COUNT_MISMATCH",
            label,
            [],
            (
                f"the runs admit different numbers of in-window modes ({len(a)} and {len(b)}); "
                f"pairing a prefix would assume which mode is missing, so no comparison is reported"
            ),
            freqs_a,
            freqs_b,
        )

    by_frequency = list(zip(sorted(a, key=lambda r: r.frequency_GHz), sorted(b, key=lambda r: r.frequency_GHz)))
    by_participation = list(
        zip(
            sorted(a, key=lambda r: -r.abs_participation(port)),
            sorted(b, key=lambda r: -r.abs_participation(port)),
        )
    )
    frequency_pairing = {(x.mode, y.mode) for x, y in by_frequency}
    participation_pairing = {(x.mode, y.mode) for x, y in by_participation}
    if frequency_pairing != participation_pairing:
        return MatchReport(
            "ORDERING_DISAGREEMENT",
            label,
            [],
            (
                f"pairing by ascending frequency gives {sorted(frequency_pairing)} but pairing by "
                f"descending |p| gives {sorted(participation_pairing)}; the correspondence is not "
                f"established by two independent orderings, so no comparison is reported"
            ),
            freqs_a,
            freqs_b,
        )

    separation_limit = 0.5 * min(_minimum_adjacent_gap(a), _minimum_adjacent_gap(b))
    pairs: list[MatchedPair] = []
    for x, y in by_frequency:
        shift = abs(x.frequency_GHz - y.frequency_GHz)
        if shift >= separation_limit:
            return MatchReport(
                "SEPARATION_GUARD",
                label,
                [],
                (
                    f"mode {x.mode} moves {shift:.6g} GHz between runs, which is not below half the "
                    f"smallest adjacent-mode spacing ({separation_limit:.6g} GHz); a swap cannot be "
                    f"excluded, so no comparison is reported"
                ),
                freqs_a,
                freqs_b,
            )
        ports = sorted(set(x.participation) | set(y.participation))
        delta_p: dict[int, float] = {}
        for j in ports:
            pa, pb = x.abs_participation(j), y.abs_participation(j)
            scale = max(pa, pb)
            delta_p[j] = abs(pa - pb) / scale if scale > 0 else 0.0
        pairs.append(
            MatchedPair(
                a=x,
                b=y,
                delta_f_relative=abs(x.frequency_GHz - y.frequency_GHz) / x.frequency_GHz,
                delta_abs_participation_relative=delta_p,
                signed_participation={
                    "a": {j: x.signed_participation(j) for j in ports},
                    "b": {j: y.signed_participation(j) for j in ports},
                },
                frequency_shift_GHz=shift,
                separation_limit_GHz=separation_limit,
            )
        )

    return MatchReport(
        "MATCHED",
        label,
        pairs,
        "the frequency and |p| orderings agree and every pair is inside the separation guard",
        freqs_a,
        freqs_b,
    )


__all__ = [
    "ADMISSION_RULE",
    "COMPARISON_CONVENTION",
    "MATCHING_RULE",
    "ROW_CORRESPONDENCE_TOLERANCE",
    "AdmissionReport",
    "AdmittedMode",
    "MatchReport",
    "MatchedPair",
    "ModeRecord",
    "ModeTableMismatch",
    "RowCorrespondenceFailure",
    "RoleAssignment",
    "RowCorrespondenceReport",
    "admit_modes",
    "check_row_correspondence",
    "join_modes_by_id",
    "label_roles",
    "match_runs",
    "unique_field_dominated",
]
