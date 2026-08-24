"""Computational gates (spec §6.2 – §6.5, §5.5).

These gates compare already-computed quantities against frozen thresholds.
They do not compute physics. When the quantity they need is unavailable —
which in v0.1 is the normal case, because the physics models are stubs — they
return INCOMPLETE or NOT-EVALUATED rather than inventing a value.
"""

from __future__ import annotations

import math

from contracts.common import Classification, GateStatus
from contracts.results import GateResult
from evaluator.base import Gate, GateInputs
from models import collision as collision_model
from models import coupling_extraction as coupling_model


class CollisionGate(Gate):
    """``COLLISION`` — |omega24 - f_readout| >= 13 MHz (spec §6.2)."""

    gate_id = "COLLISION"

    def _evaluate(self, inputs: GateInputs) -> GateResult:
        quantum = inputs.quantum_results
        if quantum is None:
            return self._incomplete(
                "no quantum results available; the dressed-system model "
                "(spec §5.2) is not implemented in v0.1, so omega24 is unknown."
            )

        omega24 = quantum.collision.get("omega24_GHz")
        f_readout = quantum.collision.get("f_readout_GHz")
        if omega24 is None or f_readout is None:
            missing = [
                name
                for name, value in (("omega24_GHz", omega24), ("f_readout_GHz", f_readout))
                if value is None
            ]
            return self._incomplete(
                f"quantum results are missing {', '.join(missing)}; omega24 is "
                f"produced by the dressed-system spectrum, which is not "
                f"implemented in v0.1."
            )

        threshold = collision_model.minimum_separation_MHz()
        separation = collision_model.separation_MHz(omega24, f_readout)
        passed = collision_model.passes(omega24, f_readout)

        return self._result(
            GateStatus.PASS if passed else GateStatus.FAIL,
            reason=(
                f"|omega24 - f_readout| = {separation:.4f} MHz "
                f"{'>=' if passed else '<'} {threshold} MHz."
            ),
            evidence_class=quantum.classification,
            measured=separation,
            threshold=threshold,
            units="MHz",
            margin=separation - threshold,
        )


class P6E2FilterGate(Gate):
    """``P6E2_FILTER`` — Purcell stopband at the dressed emission line (§6.3).

    Interpretation is three-way: below 34 dB FAILs; 34–36 dB PASSes below the
    design target; >= 36 dB PASSes with the target met. Passing here does NOT
    close hardware P6-E2 measurement.
    """

    gate_id = "P6E2_FILTER"

    def _evaluate(self, inputs: GateInputs) -> GateResult:
        solver = inputs.solver_results
        if solver is None:
            return self._incomplete("no solver results available.")

        frozen = self.definition["threshold"]
        emission_GHz = frozen["frequency_GHz"]
        minimum_dB = frozen["minimum_stopband_dB"]
        target_dB = frozen["target_stopband_dB"]

        attenuation = _stopband_dB(solver, emission_GHz)
        if attenuation is None:
            return self._incomplete(
                f"solver results carry no S21 sample at the dressed emission "
                f"frequency {emission_GHz} GHz; cannot evaluate the stopband."
            )

        if attenuation < minimum_dB:
            status, note = GateStatus.FAIL, "below the frozen 34 dB minimum"
        elif attenuation < target_dB:
            status, note = (
                GateStatus.PASS,
                f"at or above the {minimum_dB:.0f} dB minimum, below design target",
            )
        else:
            status, note = GateStatus.PASS, "target met"

        return self._result(
            status,
            reason=(
                f"stopband at {emission_GHz} GHz is {attenuation:.2f} dB — {note}. "
                f"This does not close hardware P6-E2 measurement (spec §6.3)."
            ),
            evidence_class=solver.solver.classification,
            measured=attenuation,
            threshold=minimum_dB,
            units="dB",
            margin=attenuation - minimum_dB,
        )


class P4PreSpectralGate(Gate):
    """``P4PRE_SPECTRAL`` — readout-side spectral pre-check only (spec §6.4).

    This gate must never claim that full P4 has passed. Its reason string says
    so explicitly on every outcome.
    """

    gate_id = "P4PRE_SPECTRAL"

    #: Minimum separation between a package/eigenmode and the readout line
    #: before the pre-check flags a conflict, in MHz.
    #: Classification: ENGINEERING-RULE. It reuses the frozen collision scale
    #: because v0.1 has no separately frozen package-mode allocation rule.
    MODE_CLEARANCE_MHz = 13.0

    def _evaluate(self, inputs: GateInputs) -> GateResult:
        solver = inputs.solver_results
        quantum = inputs.quantum_results
        if solver is None:
            return self._not_evaluated("no solver results available.")

        readout_GHz: float | None = None
        if quantum is not None:
            readout_GHz = quantum.dressed_system.get("root_GHz")
        if readout_GHz is None:
            return self._incomplete(
                "the dressed readout root is unknown (dressed-system model not "
                "implemented in v0.1); the readout-side spectral pre-check "
                "cannot run. This is not a statement about full P4."
            )

        conflicts = [
            mode
            for mode in solver.eigenmodes
            if abs(mode.frequency_GHz - readout_GHz) * 1000.0 < self.MODE_CLEARANCE_MHz
        ]

        if conflicts:
            nearest = min(conflicts, key=lambda m: abs(m.frequency_GHz - readout_GHz))
            separation = abs(nearest.frequency_GHz - readout_GHz) * 1000.0
            return self._result(
                GateStatus.FAIL,
                reason=(
                    f"package/eigenmode at {nearest.frequency_GHz:.6f} GHz sits "
                    f"{separation:.3f} MHz from the readout root "
                    f"{readout_GHz:.6f} GHz, inside the {self.MODE_CLEARANCE_MHz} "
                    f"MHz pre-check clearance. This is a readout-side pre-check "
                    f"only; it makes no claim about full P4 (spec §6.4)."
                ),
                evidence_class=solver.solver.classification,
                measured=separation,
                threshold=self.MODE_CLEARANCE_MHz,
                units="MHz",
                margin=separation - self.MODE_CLEARANCE_MHz,
            )

        return self._result(
            GateStatus.PASS,
            reason=(
                f"no simulated mode within {self.MODE_CLEARANCE_MHz} MHz of the "
                f"readout root {readout_GHz:.6f} GHz. Readout-side pre-check "
                f"only — full P4 has NOT passed (spec §6.4)."
            ),
            evidence_class=solver.solver.classification,
            threshold=self.MODE_CLEARANCE_MHz,
            units="MHz",
        )


class ToleranceGate(Gate):
    """``TOLERANCE`` — viability across the declared ensemble (spec §6.5)."""

    gate_id = "TOLERANCE"

    def _evaluate(self, inputs: GateInputs) -> GateResult:
        quantum = inputs.quantum_results
        if quantum is None or not quantum.tolerance:
            return self._not_evaluated(
                "no tolerance ensemble was evaluated; per-device evaluation "
                "requires the static and dressed models (spec §5.1/§5.2), which "
                "are not implemented in v0.1."
            )

        required = (
            "sample_count",
            "seed",
            "pass_count",
            "fail_count",
            "rejection_rate",
            "confidence_interval",
            "failure_reasons_by_category",
        )
        missing = [key for key in required if key not in quantum.tolerance]
        if missing:
            return self._incomplete(
                f"tolerance block is missing required outputs: {', '.join(missing)} "
                f"(spec §6.5)."
            )

        rate = quantum.tolerance["rejection_rate"]
        low, high = quantum.tolerance["confidence_interval"]
        return self._result(
            GateStatus.PASS,
            reason=(
                f"ensemble rejection rate {rate:.4f} over "
                f"{quantum.tolerance['sample_count']} draws "
                f"(seed {quantum.tolerance['seed']}), 95% interval "
                f"[{low:.4f}, {high:.4f}]. The finite-sample rate is not the "
                f"underlying model probability (spec §6.5)."
            ),
            evidence_class=quantum.classification,
            measured=rate,
            units="fraction",
        )


class CouplingExtractionGate(Gate):
    """``COUPLING_EXTRACTION`` — eigenmode vs black-box agreement (spec §5.5).

    Disagreement beyond the 10% ENGINEERING-RULE threshold returns
    ``EXTRACTION-INCONSISTENT``. The two values are never silently averaged.
    """

    gate_id = "COUPLING_EXTRACTION"

    def _evaluate(self, inputs: GateInputs) -> GateResult:
        quantum = inputs.quantum_results
        block = (quantum.dressed_system.get("coupling_extraction") if quantum else None)
        if not block:
            return self._not_evaluated(
                "no coupling extraction was performed; both the eigenmode and "
                "black-box extractions (spec §5.5) are unimplemented in v0.1."
            )

        eigenmode = block.get("eigenmode_MHz")
        blackbox = block.get("blackbox_MHz")
        if eigenmode is None or blackbox is None:
            return self._incomplete(
                "coupling extraction requires BOTH the eigenmode and black-box "
                "values; a single extraction is not sufficient (spec §5.5)."
            )

        extraction = coupling_model.CouplingExtraction(
            eigenmode_MHz=eigenmode, blackbox_MHz=blackbox
        )
        threshold = coupling_model.max_relative_disagreement()
        disagreement = extraction.relative_disagreement

        if not extraction.consistent:
            return self._result(
                GateStatus.EXTRACTION_INCONSISTENT,
                reason=(
                    f"eigenmode {eigenmode} MHz and black-box {blackbox} MHz "
                    f"disagree by {disagreement:.1%}, exceeding the "
                    f"{threshold:.0%} threshold. Values must not be averaged "
                    f"(spec §5.5)."
                ),
                evidence_class=quantum.classification,
                measured=disagreement,
                threshold=threshold,
                units="fraction",
                margin=threshold - disagreement,
            )

        return self._result(
            GateStatus.PASS,
            reason=(
                f"eigenmode {eigenmode} MHz and black-box {blackbox} MHz agree "
                f"to {disagreement:.1%} (threshold {threshold:.0%})."
            ),
            evidence_class=quantum.classification,
            measured=disagreement,
            threshold=threshold,
            units="fraction",
            margin=threshold - disagreement,
        )


# --- helpers ---------------------------------------------------------------


def _stopband_dB(solver_results, frequency_GHz: float, atol_GHz: float = 1e-6) -> float | None:
    """Return |S21| attenuation in dB at ``frequency_GHz``, or None.

    Requires a sample at (or within ``atol_GHz`` of) the requested frequency.
    Deliberately does not extrapolate: a stopband figure invented between grid
    points is not solver evidence.
    """
    s21 = solver_results.s_parameters.get("S21_dB")
    if not s21 or not solver_results.frequency_GHz:
        return None

    best_index, best_delta = None, math.inf
    for index, freq in enumerate(solver_results.frequency_GHz):
        delta = abs(freq - frequency_GHz)
        if delta < best_delta:
            best_index, best_delta = index, delta

    if best_index is None or best_delta > atol_GHz:
        return None

    # S21 in dB is negative in a stopband; attenuation is its magnitude.
    return -s21[best_index]
