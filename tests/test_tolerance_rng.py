"""RNG / tolerance convention tests (spec §12.4)."""

from __future__ import annotations

import numpy as np
import pytest

from contracts import master
from models import PhysicsNotImplemented
from models import tolerance

SEED = 20260824


def test_convention_declares_default_rng():
    assert tolerance.convention()["rng"] == "numpy.random.default_rng"


def test_sigma_is_two_percent_on_each_parameter():
    sigma = tolerance.convention()["sigma_fraction"]
    assert sigma == {"EC": 0.02, "EJ": 0.02, "EL": 0.02}


def test_draw_order_is_EC_EJ_EL():
    assert tolerance.draw_order() == ["EC", "EJ", "EL"]


def test_same_seed_reproduces_the_draw_stream():
    assert tolerance.draw_ensemble(SEED, 25) == tolerance.draw_ensemble(SEED, 25)


def test_different_seeds_differ():
    assert tolerance.draw_ensemble(SEED, 10) != tolerance.draw_ensemble(SEED + 1, 10)


def test_draw_order_is_load_bearing():
    """Drawing in a different order must not reproduce the declared stream."""
    nominal = tolerance.nominal_parameters()
    sigma = master.get("tolerance_rng_convention.sigma_fraction")

    rng = np.random.default_rng(SEED)
    reordered = {}
    for name in ["EL", "EJ", "EC"]:  # deliberately wrong order
        reordered[name] = nominal[name] * (1.0 + rng.normal(0.0, sigma[name]))

    declared = tolerance.draw_ensemble(SEED, 1)[0]
    assert reordered["EC"] != pytest.approx(declared["EC"])


def test_draws_are_centred_on_nominal_values():
    nominal = tolerance.nominal_parameters()
    devices = tolerance.draw_ensemble(SEED, 20000)
    for name, value in nominal.items():
        mean = float(np.mean([d[name] for d in devices]))
        assert mean == pytest.approx(value, rel=1e-3)


def test_draw_spread_matches_declared_sigma():
    nominal = tolerance.nominal_parameters()
    devices = tolerance.draw_ensemble(SEED, 20000)
    for name, value in nominal.items():
        std = float(np.std([d[name] for d in devices]))
        assert std / value == pytest.approx(0.02, rel=2e-2)


def test_convention_does_not_claim_legacy_reproduction():
    """Never describable as exact reproduction of legacy AMD-C samples (§4.6)."""
    assert tolerance.convention()["reproduces_legacy_finite_samples"] is False


def test_reporting_reference_is_carried():
    reference = tolerance.reporting_reference()
    assert reference["pooled_rejection_rate"] == 0.0666
    assert reference["wilson_95"] == {"low": 0.0612, "high": 0.0721}
    assert reference["draws"] == 20
    assert reference["devices_per_draw"] == 400


def test_wilson_interval_matches_frozen_reporting_reference():
    """20 draws x 400 devices at the pooled rate reproduces the frozen interval."""
    reference = tolerance.reporting_reference()
    trials = reference["draws"] * reference["devices_per_draw"]
    successes = round(reference["pooled_rejection_rate"] * trials)
    low, high = tolerance.wilson_interval(successes, trials)
    assert low == pytest.approx(reference["wilson_95"]["low"], abs=5e-4)
    assert high == pytest.approx(reference["wilson_95"]["high"], abs=5e-4)


def test_wilson_interval_rejects_impossible_inputs():
    with pytest.raises(ValueError):
        tolerance.wilson_interval(5, 0)
    with pytest.raises(ValueError):
        tolerance.wilson_interval(11, 10)


def test_ensemble_evaluation_not_implemented():
    with pytest.raises(PhysicsNotImplemented):
        tolerance.evaluate_ensemble(SEED, 10)
