"""Route A inversion: gauge invariance, identifiability and recovery.

These are software tests on synthetic circuits with known parameters. They are
not coupled EM evidence and they read no Route B quantity.
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pytest

from models.route_a_inversion import (
    FLUX_QUANTUM_WB,
    PLANCK_J_S,
    NormalModeData,
    RouteAInversionError,
    TwoNodeCircuit,
    charging_energy_GHz,
    circuit_from_design,
    coupling_GHz,
    forward_two_node,
    invert_two_node,
)
from orchestrator import manifest

REPO_ROOT = Path(__file__).resolve().parents[1]
L_F_H = (FLUX_QUANTUM_WB / (2.0 * math.pi)) ** 2 / (PLANCK_J_S * 1.58e9)

#: (f_F GHz, f_R GHz, g GHz)
DESIGNS = [
    (2.7539, 4.301974466, 0.150),
    (2.7539, 4.301974466, 0.600),
    (2.7539, 4.301974466, 0.005),
    (4.2500, 4.301974466, 0.150),
    (1.0000, 8.000000000, 0.150),
    (4.3020, 2.753900000, 0.150),
]
GAUGES = [1.0, 1.0e-4, 1.7e-2, 53.0, 1.0e4]


@pytest.fixture(scope="module")
def demo_script():
    path = REPO_ROOT / "scripts" / "route_a_synthetic_demo.py"
    spec = importlib.util.spec_from_file_location("route_a_synthetic_demo", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _design(i: int = 0) -> TwoNodeCircuit:
    f_F, f_R, g = DESIGNS[i]
    return circuit_from_design(f_F_GHz=f_F, f_R_GHz=f_R, g_GHz=g, L_F_H=L_F_H)


# --- the gauge freedom itself -------------------------------------------------


@pytest.mark.parametrize("s", GAUGES)
def test_gauge_transformation_leaves_every_observable_invariant(s):
    base = _design()
    a, b = forward_two_node(base), forward_two_node(base.gauge_transform(s))
    assert b.f_plus_GHz == pytest.approx(a.f_plus_GHz, rel=1e-12)
    assert b.f_minus_GHz == pytest.approx(a.f_minus_GHz, rel=1e-12)
    assert b.p_plus_F == pytest.approx(a.p_plus_F, rel=1e-10)
    assert b.p_minus_F == pytest.approx(a.p_minus_F, rel=1e-10)


@pytest.mark.parametrize("s", GAUGES)
def test_gauge_transformation_leaves_the_invariant_triple_invariant(s):
    base = _design()
    rel = base.invariants().relative_difference(base.gauge_transform(s).invariants())
    assert max(rel.values()) < 1e-12


def test_the_raw_readout_entries_are_not_identifiable():
    """The witness that forced the correction: same data, different entries."""
    base = _design()
    entries = [(c.c_FR, c.c_RR, c.L_R) for c in (base.gauge_transform(s) for s in GAUGES)]
    spread = max(e[2] for e in entries) / min(e[2] for e in entries)
    assert spread > 1e10, "the gauge must move L_R over many decades"
    # ... while every observable is identical.
    observed = [forward_two_node(base.gauge_transform(s)).as_dict() for s in GAUGES]
    for key in ("f_plus_GHz", "f_minus_GHz", "p_plus_F"):
        values = [o[key] for o in observed]
        assert max(values) - min(values) <= abs(values[0]) * 1e-10


def test_the_coupling_formula_matches_its_definition():
    """g from the invariant closed form equals 8 E_C,FR n_zpf,R computed directly."""
    c = _design()
    E_C_FR = charging_energy_GHz(c.c_FR)
    E_C_RR = charging_energy_GHz(c.c_RR)
    E_L_R = (FLUX_QUANTUM_WB / (2.0 * math.pi)) ** 2 / (c.L_R * PLANCK_J_S) / 1e9
    direct = 8.0 * E_C_FR * (E_L_R / (32.0 * E_C_RR)) ** 0.25
    assert coupling_GHz(c.k, c.b, c.L_F) == pytest.approx(direct, rel=1e-12)


# --- recovery -----------------------------------------------------------------


@pytest.mark.parametrize("i", range(len(DESIGNS)))
@pytest.mark.parametrize("s", GAUGES)
def test_recovers_the_known_invariants_from_noiseless_data(i, s):
    circuit = _design(i)
    truth = circuit.invariants()
    got, diag = invert_two_node(forward_two_node(circuit.gauge_transform(s)))
    assert max(truth.relative_difference(got).values()) < 1e-9
    assert diag["accepted_forward_residual"] < 1e-9
    assert len(diag["roots"]) == 2 and any("rejected" in r for r in diag["roots"])


def test_the_sum_rule_holds_and_makes_the_second_participation_dependent():
    for i in range(len(DESIGNS)):
        data = forward_two_node(_design(i))
        assert data.sum_rule_residual < 1e-12
        assert data.p_minus_F == pytest.approx(1.0 - data.p_plus_F, abs=1e-12)


def test_a_violated_sum_rule_is_reported_not_absorbed():
    data = forward_two_node(_design())
    broken = NormalModeData(data.f_plus_GHz, data.f_minus_GHz, data.p_plus_F, 0.5, L_F_H)
    with pytest.raises(RouteAInversionError, match="sum rule"):
        invert_two_node(broken)


def test_unhybridised_modes_are_reported_as_unidentifiable():
    data = forward_two_node(_design())
    for p in (0.0, 1.0):
        with pytest.raises(RouteAInversionError, match="not identifiable"):
            invert_two_node(NormalModeData(data.f_plus_GHz, data.f_minus_GHz, p, 1.0 - p, L_F_H),
                            check_sum_rule=False)


def test_data_that_are_not_a_two_node_circuit_raise_rather_than_returning_a_number():
    # A participation far too large for the observed splitting.
    with pytest.raises(RouteAInversionError):
        invert_two_node(NormalModeData(4.30, 4.2999, 0.5, 0.5, L_F_H), check_sum_rule=False)


def test_the_inversion_never_reads_a_route_b_quantity():
    """Static guard: the module must not import or mention Route B objects."""
    text = (REPO_ROOT / "models" / "route_a_inversion.py").read_text()
    for forbidden in ("port-S", "port_s", "s_parameters", "z_parameters", "blackbox", "admittance"):
        assert forbidden not in text.lower().replace("no route b quantity", "")
    assert "models.coupling_extraction" not in text
    # The module's only imports are from the standard library.
    imports = [l.strip() for l in text.splitlines() if l.startswith(("import ", "from "))]
    assert imports == ["from __future__ import annotations", "import math",
                       "from dataclasses import dataclass", "from typing import Any"]


# --- error propagation --------------------------------------------------------


def test_coupling_error_tracks_the_participation_error_not_the_frequency_error():
    """The measured propagation behaviour the numerical plan relies on."""
    import random

    circuit = _design()
    truth = circuit.invariants()
    clean = forward_two_node(circuit)

    def p95(sigma_f: float, sigma_p: float) -> float:
        rng = random.Random(4242)
        errs = []
        for _ in range(300):
            f_plus = clean.f_plus_GHz * (1.0 + rng.gauss(0.0, sigma_f))
            f_minus = clean.f_minus_GHz * (1.0 + rng.gauss(0.0, sigma_f))
            p_plus = min(max(clean.p_plus_F * (1.0 + rng.gauss(0.0, sigma_p)), 1e-15), 1 - 1e-15)
            got, _ = invert_two_node(
                NormalModeData(f_plus, f_minus, p_plus, 1.0 - p_plus, L_F_H), check_sum_rule=False
            )
            errs.append(truth.relative_difference(got)["g_GHz"])
        errs.sort()
        return errs[int(0.95 * (len(errs) - 1))]

    # Participation error dominates and scales roughly one-for-one.
    assert 0.5 <= p95(1e-6, 1e-2) / 1e-2 <= 2.0
    assert 0.5 <= p95(1e-6, 1e-3) / 1e-3 <= 2.0
    # A hundredfold looser frequency at fixed participation barely moves it.
    assert p95(1e-4, 1e-2) < 3.0 * p95(1e-6, 1e-2)


# --- the recorded demonstration ----------------------------------------------


def test_demo_writes_a_verifiable_record_and_declares_it_synthetic(demo_script, tmp_path):
    rc = demo_script.main(["--results-root", str(tmp_path), "--record-name", "demo"])
    assert rc == 0
    root = tmp_path / "demo"
    assert manifest.verify(root) == []
    summary = json.loads((root / "summary.json").read_text())
    assert summary["reads_route_b"] is False
    assert "no Palace solve" in summary["statement"] and "not evidence" in summary["statement"]
    assert summary["worst_recovery_relative_error"] < 1e-9
    assert summary["identifiability_witness"]["L_R_spread_factor"] > 1e10
    assert {e["case"] for e in summary["recovery"]} == {c[0] for c in demo_script.CASES}
    for entry in summary["propagation"]:
        assert entry["failures"] == 0
    report = (root / "report.md").read_text()
    assert "Identifiability witness" in report and "10 % agreement rule, which is unchanged" in report
