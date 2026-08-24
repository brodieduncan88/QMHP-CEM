"""Physics regression pins (spec §12.3).

QMHP-CEM v0.1 implements NO physics models. These tests therefore assert two
things:

1. every frozen regression pin is present and carries the exact specified
   value, at the specified tolerance;
2. each unimplemented model fails loudly and names the pins it must reproduce,
   rather than returning a plausible number.

When a model is implemented, replace its ``raises`` test with a comparison
against the pin at ``RELATIVE_TOLERANCE``. Do not weaken tolerances merely to
make CI pass (spec §12.3).
"""

from __future__ import annotations

import pytest

from contracts import master
from models import PhysicsNotImplemented
from models import collision, dressed_system, fluxonium, purcell

RELATIVE_TOLERANCE = 1e-6


def test_regression_tolerance_is_declared():
    assert master.get("regression_pins.relative_tolerance") == RELATIVE_TOLERANCE


@pytest.mark.parametrize(
    ("pin", "expected"),
    [
        ("dressed_root_10_12_GHz", 4.301974466),
        ("dressed_root_14_25_GHz", 4.301975383),
        ("f8_purcell_weight", 0.01182198),
        ("perturbative_root_GHz", 4.314628047),
        ("sink_line_GHz", 4.310696),
        ("sink_logical_contrast_MHz", 18.228),
    ],
)
def test_scalar_regression_pins(pin, expected):
    actual = master.get(f"regression_pins.pins.{pin}")
    assert actual == pytest.approx(expected, rel=RELATIVE_TOLERANCE)


def test_eq7_chi_regression_pin():
    chi = master.get("regression_pins.pins.eq7_chi_MHz")
    assert list(chi) == pytest.approx(
        [-5.366823, -0.305447, 7.214942], rel=RELATIVE_TOLERANCE
    )


def test_extra_precision_pins_are_verified_computational():
    """The extra pull digits are VERIFIED-COMPUTATIONAL, not printed Master values."""
    extra = master.get("regression_pins.extra_precision_pins")
    assert extra["classification"] == "VERIFIED-COMPUTATIONAL"
    assert extra["logical_pull_MHz"] == pytest.approx(-9.507089, rel=RELATIVE_TOLERANCE)
    assert extra["sink_pull_MHz"] == pytest.approx(8.721155, rel=RELATIVE_TOLERANCE)


def test_master_display_pulls_are_three_decimals():
    refs = master.get("dressed_system.physical_pull_references")
    assert refs["logical_pull_MHz_master_display"] == -9.507
    assert refs["sink_pull_MHz_master_display"] == 8.721


def test_truncation_shift_is_not_an_error_condition():
    production = master.get("dressed_system.production_convention.root_GHz")
    spot_check = master.get("dressed_system.high_truncation_spot_check.root_GHz")
    shift_kHz = (spot_check - production) * 1e6
    assert shift_kHz == pytest.approx(0.92, abs=0.01)
    assert master.get("dressed_system.truncation_shift_kHz_expected") == 0.92


# --- unimplemented models fail loudly ---------------------------------------


def test_static_fluxonium_not_implemented():
    with pytest.raises(PhysicsNotImplemented) as exc:
        fluxonium.solve_static()
    assert "5.1" in str(exc.value)
    assert "f01_GHz" in str(exc.value)


def test_dressed_root_not_implemented():
    with pytest.raises(PhysicsNotImplemented) as exc:
        dressed_system.solve_dressed_root()
    assert "4.301974466" in str(exc.value)


def test_high_truncation_spot_check_not_implemented():
    with pytest.raises(PhysicsNotImplemented):
        dressed_system.solve_dressed_root(
            dressed_system.SPOT_CHECK_NQ, dressed_system.SPOT_CHECK_NPH
        )


def test_purcell_weight_not_implemented():
    with pytest.raises(PhysicsNotImplemented) as exc:
        purcell.purcell_weight()
    assert "0.01182198" in str(exc.value)


def test_omega24_not_implemented():
    with pytest.raises(PhysicsNotImplemented):
        collision.omega24()


# --- the bare-admixture guard (spec §4.5, §5.3) -----------------------------


def test_bare_admixture_substitution_is_rejected():
    with pytest.raises(ValueError, match="bare-admixture"):
        purcell.assert_not_bare_admixture(purcell.bare_admixture_reference())


def test_correct_dressed_weight_is_accepted():
    purcell.assert_not_bare_admixture(purcell.dressed_weight_pin())


def test_frozen_phase_grid_convention():
    grid = fluxonium.phase_grid_convention()
    assert grid["grid_points"] == 3201
    assert grid["kinetic_operator"] == "second_difference"
