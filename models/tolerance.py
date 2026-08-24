"""Tolerance ensemble (spec §5.4).

The RNG *convention* is a QMHP-CEM-NORMATIVE convention rather than physics, so
it is implemented here. What is NOT implemented is the per-draw device
evaluation, which requires the static and dressed models (spec §5.1/§5.2).

This convention must never be described as exact reproduction of legacy AMD-C
finite samples (spec §4.6). Legacy exact finite-sample identities and counts
are not reproducibility targets.
"""

from __future__ import annotations

from typing import Any, Iterator

import numpy as np

from contracts import master


def convention() -> dict[str, Any]:
    """The frozen CEM RNG convention (spec §4.6)."""
    conv = master.get("tolerance_rng_convention")
    return {
        "rng": conv["rng"],
        "sigma_fraction": dict(conv["sigma_fraction"]),
        "draw_order": list(conv["draw_order"]),
        "reproduces_legacy_finite_samples": conv["reproduces_legacy_finite_samples"],
    }


def draw_order() -> list[str]:
    """Parameter draw order: EC -> EJ -> EL."""
    return list(master.get("tolerance_rng_convention.draw_order"))


def nominal_parameters() -> dict[str, float]:
    """Branch-A nominal EC/EJ/EL in GHz (spec §4.1)."""
    dev = master.get("branch_a_device")
    return {
        "EC": dev["EC_over_h_GHz"],
        "EJ": dev["EJ_over_h_GHz"],
        "EL": dev["EL_over_h_GHz"],
    }


def draw_ensemble(seed: int, n_devices: int) -> list[dict[str, float]]:
    """Draw a device ensemble under the frozen CEM convention.

    Independent Gaussian fractional perturbations, sigma = 2% for EC, EJ and
    EL, drawn strictly in the order EC -> EJ -> EL from
    ``numpy.random.default_rng(seed)``.

    The draw order is load-bearing: the same seed only reproduces the same
    stream if the parameters are drawn in the declared order (spec §12.4).

    Args:
        seed: RNG seed. Must be recorded in every batch/candidate manifest.
        n_devices: Number of devices to draw.

    Returns:
        A list of per-device parameter dicts in GHz.
    """
    if n_devices < 1:
        raise ValueError("n_devices must be >= 1")

    rng = np.random.default_rng(seed)
    sigma = master.get("tolerance_rng_convention.sigma_fraction")
    nominal = nominal_parameters()
    order = draw_order()

    devices: list[dict[str, float]] = []
    for _ in range(n_devices):
        device: dict[str, float] = {}
        # Draw strictly in the declared order; one normal per parameter.
        for name in order:
            fractional = rng.normal(0.0, sigma[name])
            device[name] = nominal[name] * (1.0 + fractional)
        devices.append(device)
    return devices


def draw_stream(seed: int, n_devices: int) -> Iterator[dict[str, float]]:
    """Iterator form of :func:`draw_ensemble`."""
    yield from draw_ensemble(seed, n_devices)


def reporting_reference() -> dict[str, Any]:
    """Frozen ensemble reporting reference (spec §4.6).

    This is a reporting reference, not a reproducibility target.
    """
    ref = master.get("fabrication_ensemble")
    return {
        "pooled_rejection_rate": ref["pooled_rejection_rate"],
        "wilson_95": dict(ref["wilson_95"]),
        "draws": ref["draws"],
        "devices_per_draw": ref["devices_per_draw"],
    }


def wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Reported alongside every finite-sample rejection rate so that a single
    finite-sample count is never presented as the underlying model probability
    (spec §6.5).
    """
    if trials <= 0:
        raise ValueError("trials must be positive")
    if not 0 <= successes <= trials:
        raise ValueError("successes must lie in [0, trials]")
    p = successes / trials
    denom = 1.0 + z**2 / trials
    centre = (p + z**2 / (2 * trials)) / denom
    half = (z / denom) * np.sqrt(p * (1 - p) / trials + z**2 / (4 * trials**2))
    return (float(max(0.0, centre - half)), float(min(1.0, centre + half)))


def evaluate_ensemble(seed: int, n_devices: int) -> dict[str, Any]:
    """Evaluate candidate viability across the tolerance ensemble (spec §6.5).

    Each drawn device is screened against the frozen 13 MHz collision gate.

    Cost warning: every device requires a full static solve plus a bracketed
    dressed-root search, roughly half a second each. A 400-device ensemble is
    minutes, not seconds. Callers driving a sweep should size ``n_devices``
    deliberately.

    Returns the outputs spec §6.5 requires: sample count, seed, pass and fail
    counts, rejection rate, confidence interval and failure reasons by
    category. The finite-sample rate is NOT the underlying model probability;
    the Wilson interval is reported alongside it for that reason.
    """
    from models import collision
    from models.dressed_system import RootNotBracketed

    devices = draw_ensemble(seed, n_devices)
    failures: dict[str, int] = {}
    passed = 0

    unscreened = 0
    for device in devices:
        try:
            result = collision.screen(
                EC_GHz=device["EC"], EJ_GHz=device["EJ"], EL_GHz=device["EL"]
            )
        except RootNotBracketed:
            # Not a pass and not a collision rejection: this device was never
            # screened. Counting it either way would misstate the rate.
            unscreened += 1
            failures["root_not_bracketed"] = failures.get("root_not_bracketed", 0) + 1
            continue
        if result["passes"]:
            passed += 1
        else:
            failures["collision_below_13MHz"] = (
                failures.get("collision_below_13MHz", 0) + 1
            )

    rejected = n_devices - passed - unscreened
    screened = passed + rejected
    low, high = wilson_interval(rejected, screened) if screened else (0.0, 1.0)

    return {
        "sample_count": n_devices,
        "screened_count": screened,
        "unscreened_count": unscreened,
        "seed": seed,
        "pass_count": passed,
        "fail_count": rejected,
        "rejection_rate": (rejected / screened) if screened else None,
        "confidence_interval": [low, high],
        "failure_reasons_by_category": failures,
        "convention": convention(),
        "note": (
            "Finite-sample rate, not the underlying model probability. This "
            "ensemble uses the QMHP-CEM normative RNG convention and does not "
            "reproduce legacy AMD-C finite samples."
        ),
    }
