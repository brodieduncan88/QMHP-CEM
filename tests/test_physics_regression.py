"""Physics regression tests (spec §12.3).

The physics models are implemented against the frozen conventions and tested
against the frozen pins. Pins are grouped by the precision an independent
implementation actually attains — see ``master/qmhp_v158f_requirements.yaml``,
``regression_pins`` — and each group is asserted at its own recorded tolerance.

No tolerance here is chosen to make a test pass. The three
``cross_implementation`` pins carry a measured deviation above the declared
1e-6 and are asserted at the measured agreement while explicitly flagged; see
``docs/regression-pins.md``.
"""

from __future__ import annotations

import numpy as np
import pytest

from contracts import master
from models import collision, dressed_system, fluxonium, purcell

DECLARED_TOLERANCE = 1e-6


@pytest.fixture(scope="module")
def spectrum():
    return fluxonium.nominal_spectrum()


@pytest.fixture(scope="module")
def dressed():
    return dressed_system.dressed_spectrum()


def pins(group: str) -> dict:
    return dict(master.get(f"regression_pins.{group}.pins"))


# --- declared tolerance -----------------------------------------------------


def test_declared_tolerance_is_unchanged():
    """The headline tolerance must not drift (spec §12.3)."""
    assert master.get("regression_pins.relative_tolerance") == DECLARED_TOLERANCE


# --- exact pins -------------------------------------------------------------


def test_static_f01(spectrum):
    assert spectrum.f(1) == pytest.approx(0.175710013, rel=DECLARED_TOLERANCE)


def test_static_f02(spectrum):
    assert spectrum.f(2) == pytest.approx(3.581724312, rel=DECLARED_TOLERANCE)


def test_sin_delta_over_2(spectrum):
    """Reproduces exactly, and only with the (phi - phi_ext) convention."""
    assert spectrum.sin_delta_over_2(0, 2) == pytest.approx(
        0.295705232, rel=DECLARED_TOLERANCE
    )


def test_sin_convention_is_load_bearing(spectrum):
    """Without the phi_ext offset the element vanishes by parity."""
    wrong = abs(
        np.sum(
            spectrum.eigenvectors[:, 0]
            * np.sin(spectrum.phase_grid / 2)
            * spectrum.eigenvectors[:, 2]
        )
    )
    assert wrong < 1e-9
    assert spectrum.sin_delta_over_2(0, 2) > 0.29


def test_n02_is_at_the_numerical_floor(spectrum):
    assert master.get("static_fluxonium.reference_values.n02") == "numerical_floor"
    assert spectrum.n(0, 2) < 1e-9


def test_dressed_root_production_truncation():
    assert dressed_system.nominal_root(10, 12) == pytest.approx(
        4.301974466, rel=DECLARED_TOLERANCE
    )


@pytest.mark.slow
def test_dressed_root_high_truncation_spot_check():
    """The (14, 25) ladder point. Slower: larger Hilbert space."""
    assert dressed_system.solve_dressed_root(
        14, 25, bracket=dressed_system.NOMINAL_BRACKET
    ) == pytest.approx(4.301975383, rel=DECLARED_TOLERANCE)


def test_truncation_shift_is_not_an_error_condition():
    production = master.get("dressed_system.production_convention.root_GHz")
    spot = master.get("dressed_system.high_truncation_spot_check.root_GHz")
    assert (spot - production) * 1e6 == pytest.approx(0.92, abs=0.01)


# --- display-precision pins -------------------------------------------------


def test_sink_line_at_printed_precision(dressed):
    assert round(dressed["sink_line_GHz"], 6) == 4.310696


def test_dressed_f12_at_printed_precision(dressed):
    assert round(dressed["dressed_f12_GHz"], 6) == 3.395056


def test_sink_logical_contrast_at_printed_precision(dressed):
    """18.228 is a three-decimal Master display value (spec §12.3 carve-out)."""
    assert round(dressed["sink_logical_contrast_MHz"], 3) == 18.228


def test_n12_at_printed_precision(spectrum):
    assert round(spectrum.n(1, 2), 6) == 0.659915


def test_display_pins_would_fail_at_1e6(dressed):
    """Documents WHY these are display-precision pins rather than exact ones.

    If this ever starts passing at 1e-6, the pins should be promoted to the
    exact group rather than left here.
    """
    contrast = dressed["sink_logical_contrast_MHz"]
    assert abs(contrast - 18.228) / 18.228 > DECLARED_TOLERANCE


# --- cross-implementation pins (FLAGGED) ------------------------------------


def test_cross_implementation_group_is_flagged():
    group = master.get("regression_pins.cross_implementation")
    assert group["status"] == "FLAGGED-FOR-REVIEW"
    assert group["tolerance"] > DECLARED_TOLERANCE


@pytest.mark.parametrize(
    ("pin", "getter"),
    [
        ("f8_purcell_weight", lambda d: d["purcell_weight"]),
        ("sink_pull_MHz", lambda d: d["sink_pull_MHz"]),
        ("logical_pull_MHz", lambda d: d["logical_pull_MHz"]),
    ],
)
def test_cross_implementation_pins(dressed, pin, getter):
    """Asserted at the MEASURED cross-implementation agreement, not a guess."""
    recorded = master.get(f"regression_pins.cross_implementation.pins.{pin}")
    tolerance = master.get("regression_pins.cross_implementation.tolerance")
    assert getter(dressed) == pytest.approx(recorded["value"], rel=tolerance)


@pytest.mark.parametrize(
    ("pin", "getter"),
    [
        ("f8_purcell_weight", lambda d: d["purcell_weight"]),
        ("sink_pull_MHz", lambda d: d["sink_pull_MHz"]),
    ],
)
def test_flagged_pins_still_miss_the_declared_tolerance(dressed, pin, getter):
    """The recorded deviation is real. If this fails, the flag can be lifted."""
    recorded = master.get(f"regression_pins.cross_implementation.pins.{pin}")
    deviation = abs(getter(dressed) - recorded["value"]) / abs(recorded["value"])
    assert deviation > DECLARED_TOLERANCE
    assert deviation == pytest.approx(
        recorded["observed_relative_deviation"], rel=0.05
    )


def test_observed_values_are_reproduced_exactly(dressed):
    """The recorded observed_value must match what the model computes now."""
    group = master.get("regression_pins.cross_implementation.pins")
    assert dressed["purcell_weight"] == pytest.approx(
        group["f8_purcell_weight"]["observed_value"], rel=1e-8
    )
    assert dressed["sink_pull_MHz"] == pytest.approx(
        group["sink_pull_MHz"]["observed_value"], rel=1e-8
    )
    assert dressed["logical_pull_MHz"] == pytest.approx(
        group["logical_pull_MHz"]["observed_value"], rel=1e-8
    )


# --- unverified pins --------------------------------------------------------


def test_unverified_pins_are_marked_and_carried():
    group = master.get("regression_pins.unverified")
    assert group["status"] == "NO-REFERENCE-IMPLEMENTATION"
    assert group["pins"]["perturbative_root_GHz"] == 4.314628047
    assert list(group["pins"]["eq7_chi_MHz"]) == [-5.366823, -0.305447, 7.214942]


def test_eq7_is_a_diagnostic_not_the_operating_point():
    """The perturbative root must never be reported as the operating point."""
    perturbative = master.get("eq7_diagnostic.perturbative_root_GHz")
    exact = dressed_system.nominal_root()
    assert abs(perturbative - exact) * 1e3 > 12.0


# --- Purcell ----------------------------------------------------------------


def test_purcell_weight_is_computed_not_substituted():
    weight = purcell.purcell_weight()
    bare = purcell.bare_admixture_reference()
    assert abs(weight - bare) / bare > 1e-4


def test_bare_admixture_substitution_is_rejected():
    with pytest.raises(ValueError, match="bare-admixture"):
        purcell.assert_not_bare_admixture(purcell.bare_admixture_reference())


def test_purcell_rate_requires_an_explicit_kappa():
    """No default kappa: assuming one fabricates what the filter gate tests."""
    import inspect

    signature = inspect.signature(purcell.purcell_rate)
    assert signature.parameters["kappa_at_emission_Hz"].default is inspect.Parameter.empty


def test_emission_frequency_is_the_filter_target():
    assert round(purcell.emission_frequency_GHz(), 6) == master.get(
        "purcell_f8.filter_constraint.dressed_emission_GHz"
    )


# --- collision --------------------------------------------------------------


def test_nominal_device_clears_the_collision_gate():
    result = collision.screen()
    assert result["passes"] is True
    assert result["separation_MHz"] > 90.0


def test_omega24_is_above_the_readout_root():
    assert collision.omega24() > collision.readout_root_GHz()


def test_perturbed_device_can_fail_the_screen():
    """A device close to collision must actually be rejected."""
    from models import tolerance

    devices = tolerance.draw_ensemble(20260725, 3)
    near = devices[1]
    result = collision.screen(
        EC_GHz=near["EC"], EJ_GHz=near["EJ"], EL_GHz=near["EL"]
    )
    assert result["passes"] is False
    assert result["separation_MHz"] < 13.0
