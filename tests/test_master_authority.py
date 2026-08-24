"""Master authority tests (spec §12.1)."""

from __future__ import annotations

import pytest

from contracts import master
from contracts.common import Classification


def test_master_files_load():
    assert master.requirements()["master_revision"] == "v1.5.8f"
    assert master.validation_gates()["schema"] == "qmhp-cem.validation-gates/0.1.0"
    assert master.provenance()["schema"] == "qmhp-cem.provenance/0.1.0"


def test_provenance_digests_match():
    assert master.verify_provenance() == []


def test_provenance_carries_master_pdf_digest():
    recorded = master.provenance()["qmhp_master_pdf_sha256"]
    assert recorded == (
        "c59c518b3956b752abe78437bfcd7d00b30c439da6fc95a7aba176156237499e"
    )
    assert master.provenance()["operative_base_v158e_sha256"] == (
        "83aeb3a2d8ebcb8f627989557350d9c172ad5bc20c3edc561b8a5e091cc4b658"
    )


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("branch_a_device.EC_over_h_GHz", 0.60),
        ("branch_a_device.EJ_over_h_GHz", 5.72),
        ("branch_a_device.EL_over_h_GHz", 1.58),
        ("static_fluxonium.phase_grid.grid_points", 3201),
        ("static_fluxonium.reference_values.f01_GHz", 0.175710013),
        ("static_fluxonium.reference_values.f02_GHz", 3.581724312),
        ("static_fluxonium.reference_values.n12", 0.659915),
        ("static_fluxonium.reference_values.sin_delta_over_2_02", 0.295705232),
        ("eq7_diagnostic.perturbative_root_GHz", 4.314628047),
        ("dressed_system.production_convention.root_GHz", 4.301974466),
        ("dressed_system.high_truncation_spot_check.root_GHz", 4.301975383),
        ("dressed_system.physical_pull_references.sink_line_GHz", 4.310696),
        ("dressed_system.physical_pull_references.dressed_f12_GHz", 3.395056),
        ("dressed_system.physical_pull_references.sink_logical_contrast_MHz", 18.228),
        ("purcell_f8.dressed_weight", 0.01182198),
        ("purcell_f8.filter_constraint.minimum_stopband_dB", 34.0),
        ("purcell_f8.filter_constraint.target_stopband_dB", 36.0),
        ("collision.minimum_abs_omega24_minus_readout_MHz", 13.0),
        ("fabrication_ensemble.pooled_rejection_rate", 0.0666),
        ("p6e6_joint_acceptance.p_induced_max_per_data_qubit_round_equivalent", 0.001),
        ("p6e6_joint_acceptance.Pu_total_max_per_round", 0.01),
        ("p6e6_joint_acceptance.logical_advantage_confidence_min", 0.95),
    ],
)
def test_frozen_values_match_specification(path, expected):
    assert master.get(path) == expected


def test_eq7_chi_values():
    chi = master.get("eq7_diagnostic.chi_MHz")
    assert chi["state_0"] == -5.366823
    assert chi["state_1"] == -0.305447
    assert chi["state_2"] == 7.214942


def test_symbolic_values_resolve():
    import math

    assert master.get("branch_a_device.phi_ext") == pytest.approx(math.pi)
    assert master.get("static_fluxonium.phase_grid.phase_min") == pytest.approx(-8 * math.pi)
    assert master.get("static_fluxonium.phase_grid.phase_max") == pytest.approx(8 * math.pi)


def test_numerical_floor_sentinel_is_not_a_number():
    assert master.get("static_fluxonium.reference_values.n02") == "numerical_floor"


def test_runtime_code_cannot_mutate_master():
    """Frozen requirements are immutable at runtime (spec §2.1, §12.1)."""
    requirements = master.requirements()
    with pytest.raises(TypeError):
        requirements["collision"] = {}  # type: ignore[index]
    with pytest.raises(TypeError):
        requirements["collision"]["minimum_abs_omega24_minus_readout_MHz"] = 0.0  # type: ignore[index]


def test_nested_sequences_are_immutable():
    pins = master.get("regression_pins.pins.eq7_chi_MHz")
    assert isinstance(pins, tuple)
    with pytest.raises(TypeError):
        pins[0] = 0.0  # type: ignore[index]


def test_candidate_processing_cannot_change_frozen_requirements(seed_candidate):
    """Processing a candidate must not perturb frozen values (spec §12.1)."""
    from evaluator import evaluate_candidate

    before = master.get("collision.minimum_abs_omega24_minus_readout_MHz")
    evaluate_candidate(seed_candidate)
    assert master.get("collision.minimum_abs_omega24_minus_readout_MHz") == before


def test_bare_admixture_is_distinct_from_dressed_weight():
    """These are different quantities and must not be conflated (spec §4.5)."""
    assert master.get("purcell_f8.dressed_weight") != master.get(
        "purcell_f8.bare_admixture_overlap_approx"
    )


def test_legacy_finite_sample_counts_are_not_reproducibility_targets():
    assert master.get(
        "fabrication_ensemble.legacy_finite_sample_counts_are_reproducibility_targets"
    ) is False
    assert master.get("tolerance_rng_convention.reproduces_legacy_finite_samples") is False


def test_matched_screen_conclusion_preserved():
    assert master.get("qec_references.matched_screen_conclusion") == (
        "NO SEPARATION ESTABLISHED"
    )


def test_gate_definitions_cover_required_gates():
    required = {
        "COLLISION",
        "P6E2_FILTER",
        "P4PRE_SPECTRAL",
        "TOLERANCE",
        "COUPLING_EXTRACTION",
        "P6E6_JOINT",
        "P0D",
        "P1",
        "P3",
        "P5",
        "P7",
    }
    assert required <= set(master.gate_definitions())


def test_unknown_gate_id_rejected():
    with pytest.raises(KeyError):
        master.gate_definition("P9_INVENTED")


def test_measured_is_the_only_hardware_closing_evidence_class():
    assert Classification.MEASURED not in __import__(
        "contracts.common", fromlist=["NON_HARDWARE_EVIDENCE"]
    ).NON_HARDWARE_EVIDENCE
