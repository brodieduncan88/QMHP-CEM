"""The port-stiffness diagnostic: derived, not fitted, and independent.

Three things are under test and they are kept apart.

1. *The derivation.* ``kappa`` is a function of the configuration and the mesh
   bounding box. These tests recompute it from the declared inputs and assert
   the value, and assert that computing it reads no solver output at all --
   which is what "not calibrated on modes whose energy balance looks
   favourable" has to mean operationally.
2. *The formula.* Synthetic port fields with closed-form integrals -- a
   uniform aligned field, a zero-mean modulated one, a transverse one, and one
   with an out-of-face component -- exercise the whole chain from probe
   integrals to port participation. A failure here is a fault in the
   conversion, not a disagreement with a solve.
3. *The record.* The committed level-2 and level-3 CSVs, checked mode by mode.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest

from solvers.palace.port_diagnostic import (
    MU0,
    PALACE_SOURCE_CITATIONS,
    UNVERIFIED_ASSUMPTIONS,
    NonDimensionalisation,
    PortConversion,
    PortGeometry,
    SyntheticPortField,
    compare,
    cosine_modulated_field,
    transverse_field,
    uniform_aligned_field,
    with_normal_component,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
L2 = REPO_ROOT / "results" / "COUPLED-LADDER-O1-L2-20260916T080802Z" / "L2" / "solver"
L3 = REPO_ROOT / "results" / "COUPLED-LADDER-O1-L3-20260916T091212Z" / "L3" / "solver"

#: The declared S1 port face: 0.02 x 0.04 mm, +Y, measured from the committed
#: meshes in tests/test_mesh_inspection.py rather than assumed here.
PORT = PortGeometry(length_mm=0.04, width_mm=0.02, n_elements=1, direction="+Y")
#: Lc is the largest mesh bounding-box extent; the S1 cell is 4 mm across.
SCALES = NonDimensionalisation(Lc_m=4.0e-3, L0_m=1.0e-3)
#: From config/coupled/v2a_five_node_candidate.json via the committed config.json.
PORT_INDUCTANCE_H = 1.0345665367517793e-07


def conversion() -> PortConversion:
    return PortConversion(
        geometry=PORT,
        scales=SCALES,
        inductance_H=PORT_INDUCTANCE_H,
        probe_thickness_mesh_units=1.0,
        probe_permittivity=1.0,
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open() as handle:
        reader = csv.reader(handle)
        header = [h.strip() for h in next(reader)]
        return [{h: v.strip() for h, v in zip(header, row)} for row in reader if row]


def _record(solver_dir: Path) -> list[dict[str, float]]:
    post = solver_dir / "postpro"
    eig = _read_csv(post / "eig.csv")
    dom = _read_csv(post / "domain-E.csv")
    sur = _read_csv(post / "surface-Q.csv")
    epr = _read_csv(post / "port-EPR.csv")
    rows = []
    for e, d, s, p in zip(eig, dom, sur, epr):
        rows.append({
            "mode": int(float(e["m"])),
            "f": float(e["Re{f} (GHz)"]),
            "E_elec": float(d["E_elec (J)"]),
            "E_mag": float(d["E_mag (J)"]),
            "E_cap": float(d["E_cap (J)"]),
            "E_ind": float(d["E_ind (J)"]),
            "p_default": float(s["p_surf[1]"]),
            "p_ma": float(s["p_surf[2]"]),
            "p_epr": float(p["p[1]"]),
        })
    return rows


# --------------------------------------------------------------------------
# 1. The derivation
# --------------------------------------------------------------------------


def test_kappa_is_computed_from_declared_inputs_only():
    """Every factor traces to the config, the mesh or a pinned source line."""
    c = conversion()
    assert c.probe_thickness_nd == pytest.approx(1.0 / 4.0)          # iodata.cpp:535
    assert c.inductance_nd == pytest.approx(PORT_INDUCTANCE_H / (MU0 * 4.0e-3))  # :512
    assert c.geometry.to_square == pytest.approx(0.02 / 0.04)        # lumpedportoperator.hpp:57-60
    assert c.sheet_inductance_nd == pytest.approx(c.inductance_nd * 0.5)
    assert c.kappa == pytest.approx(1.0 / (c.probe_thickness_nd * c.sheet_inductance_nd))
    assert c.kappa == pytest.approx(0.38868825288128767, rel=1e-12)


def test_kappa_reads_no_solver_output():
    """The prohibition is operational: nothing on disk is consulted.

    A conversion built from declared numbers alone cannot have been calibrated
    on a favourable subset of modes, because it never saw a mode.
    """
    c = PortConversion(
        geometry=PortGeometry(length_mm=0.04, width_mm=0.02),
        scales=NonDimensionalisation(Lc_m=4.0e-3, L0_m=1.0e-3),
        inductance_H=PORT_INDUCTANCE_H,
        probe_thickness_mesh_units=1.0,
        probe_permittivity=1.0,
    )
    assert math.isfinite(c.kappa)
    payload = c.as_dict()
    assert payload["kappa_definition"].endswith("derived, not fitted")
    assert "eig.csv" not in json.dumps(payload["factors"])
    assert "domain-E" not in json.dumps(payload["factors"])


def test_kappa_scales_as_the_derivation_says():
    """Doubling L halves kappa; doubling w/l halves it; doubling Lc quarters t_nd."""
    base = conversion().kappa
    doubled_L = PortConversion(
        geometry=PORT, scales=SCALES, inductance_H=2 * PORT_INDUCTANCE_H,
        probe_thickness_mesh_units=1.0, probe_permittivity=1.0,
    )
    assert doubled_L.kappa == pytest.approx(base / 2.0)
    wider = PortConversion(
        geometry=PortGeometry(length_mm=0.04, width_mm=0.04), scales=SCALES,
        inductance_H=PORT_INDUCTANCE_H, probe_thickness_mesh_units=1.0, probe_permittivity=1.0,
    )
    assert wider.kappa == pytest.approx(base / 2.0)
    two_elements = PortConversion(
        geometry=PortGeometry(length_mm=0.04, width_mm=0.02, n_elements=2), scales=SCALES,
        inductance_H=PORT_INDUCTANCE_H, probe_thickness_mesh_units=1.0, probe_permittivity=1.0,
    )
    assert two_elements.kappa == pytest.approx(base / 2.0)


def test_unequal_permittivity_is_refused():
    """``Default`` carries ``t*eps`` and ``MA`` carries ``t/eps``.

    Their difference is ``0.5 t |E_t|^2`` only at ``eps = 1``. Anything else is
    not the reduction this module derives, so it is refused rather than
    silently rescaled.
    """
    with pytest.raises(ValueError, match="permittivity"):
        PortConversion(
            geometry=PORT, scales=SCALES, inductance_H=PORT_INDUCTANCE_H,
            probe_thickness_mesh_units=1.0, probe_permittivity=11.45,
        )


def test_tc_and_omega_follow_the_pinned_definitions():
    assert SCALES.tc_ns == pytest.approx(1.0e9 * 4.0e-3 / 299792458.0, rel=1e-9)
    assert SCALES.omega(1.0) == pytest.approx(2.0 * math.pi * SCALES.tc_ns)


def test_every_factor_and_assumption_is_reported():
    payload = conversion().as_dict()
    for key in (
        "port_enters_K_as_a_boundary_mass_term", "Ls_definition", "l_and_w_definition",
        "L_nondimensionalisation", "t_nondimensionalisation", "Lc_definition",
        "tc_definition", "probe_default", "probe_ma", "probe_side_rule",
        "probe_integration", "probe_normalisation", "E_ind_is_rank_one",
    ):
        assert key in payload["source"], key
        assert ".cpp:" in payload["source"][key] or ".hpp:" in payload["source"][key]
    assert len(payload["unverified_assumptions"]) == len(UNVERIFIED_ASSUMPTIONS)
    for assumption in payload["unverified_assumptions"]:
        assert assumption["statement"]
        assert assumption["what_would_settle_it"]
    assert len(PALACE_SOURCE_CITATIONS) >= 13


# --------------------------------------------------------------------------
# 2. The formula, against fields whose integrals are known
# --------------------------------------------------------------------------


FREQUENCY_GHZ = 1.709561611
DENOMINATOR = 6.671281904e-03


def _round_trip(field, quadrature: int = 600):
    """Probe integrals -> participation, against ``E_port`` from its definition."""
    c = conversion()
    synthetic = SyntheticPortField(geometry=PORT, scales=SCALES, field=field, quadrature=quadrature)
    integral_default, integral_ma = synthetic.probe_integrals(1.0)
    from_probes = c.port_participation(
        integral_default / DENOMINATOR, integral_ma / DENOMINATOR, FREQUENCY_GHZ
    )
    direct = synthetic.port_stiffness_energy(c, FREQUENCY_GHZ) / DENOMINATOR
    return synthetic, from_probes, direct


def test_uniform_aligned_field_is_the_one_case_E_ind_gets_right():
    """``E_ind`` is exact exactly when the port field is uniform and aligned."""
    synthetic, from_probes, direct = _round_trip(uniform_aligned_field(3.0))
    assert from_probes == pytest.approx(direct, rel=1e-12)
    c = conversion()
    e_ind = synthetic.inductor_energy(c, FREQUENCY_GHZ)
    e_port = synthetic.port_stiffness_energy(c, FREQUENCY_GHZ)
    assert e_ind == pytest.approx(e_port, rel=1e-12)


@pytest.mark.parametrize("contrast", [0.25, 0.5, 0.9])
def test_controlled_non_uniform_field_matches_its_closed_form(contrast: float):
    """``E_along = A(1 + c cos(2 pi u / w))``: ``V`` unchanged, ``INT|E_t|^2`` up by 1+c^2/2."""
    synthetic, from_probes, direct = _round_trip(
        cosine_modulated_field(PORT.width_mm, 3.0, contrast), quadrature=900
    )
    assert from_probes == pytest.approx(direct, rel=1e-12)
    c = conversion()
    ratio = synthetic.inductor_energy(c, FREQUENCY_GHZ) / synthetic.port_stiffness_energy(
        c, FREQUENCY_GHZ
    )
    assert ratio == pytest.approx(1.0 / (1.0 + contrast**2 / 2.0), rel=1e-5)
    assert ratio < 1.0


def test_transverse_component_is_invisible_to_the_voltage_but_not_to_the_stiffness():
    synthetic, from_probes, direct = _round_trip(transverse_field(1.0, 2.0))
    assert from_probes == pytest.approx(direct, rel=1e-12)
    c = conversion()
    ratio = synthetic.inductor_energy(c, FREQUENCY_GHZ) / synthetic.port_stiffness_energy(
        c, FREQUENCY_GHZ
    )
    assert ratio == pytest.approx(1.0 / 5.0, rel=1e-12)


def test_the_MA_probe_removes_the_out_of_face_component_exactly():
    """A normal component must not move anything the conversion computes."""
    _, plain, direct_plain = _round_trip(uniform_aligned_field(3.0))
    _, with_normal, direct_normal = _round_trip(
        with_normal_component(uniform_aligned_field(3.0), 11.0)
    )
    assert with_normal == pytest.approx(plain, rel=1e-11)
    assert direct_normal == pytest.approx(direct_plain, rel=1e-12)


@pytest.mark.parametrize(
    "field",
    [
        uniform_aligned_field(1.0),
        cosine_modulated_field(0.02, 1.0, 0.7),
        transverse_field(1.0, 0.3),
        transverse_field(0.1, 3.0),
        with_normal_component(cosine_modulated_field(0.02, 2.0, 0.4), 5.0),
    ],
)
def test_the_surrogate_is_one_sided(field):
    """``E_ind/E_port <= 1`` by Cauchy-Schwarz, for every field.

    So a disagreement between ``E_ind`` and the port stiffness term can only
    ever be an *understatement*: the surrogate cannot overstate the port energy.
    """
    c = conversion()
    synthetic = SyntheticPortField(geometry=PORT, scales=SCALES, field=field, quadrature=500)
    ratio = synthetic.inductor_energy(c, FREQUENCY_GHZ) / synthetic.port_stiffness_energy(
        c, FREQUENCY_GHZ
    )
    assert ratio <= 1.0 + 1e-12


def test_participation_is_frequency_scaled_as_one_over_omega_squared():
    c = conversion()
    a = c.port_participation(1.0, 0.0, 2.0)
    b = c.port_participation(1.0, 0.0, 4.0)
    assert a / b == pytest.approx(4.0, rel=1e-12)


# --------------------------------------------------------------------------
# 3. The record
# --------------------------------------------------------------------------


@pytest.mark.parametrize("solver_dir", [L2, L3], ids=["L2", "L3"])
def test_the_derived_conversion_reproduces_the_closure_defect_on_every_mode(solver_dir: Path):
    """The independent evaluation lands on the closure requirement, mode by mode.

    Nothing is fitted: the same ``kappa`` is used at both levels and on all six
    modes, including the ones whose reported ``E_ind`` is wrong by six orders of
    magnitude.
    """
    c = conversion()
    rows = _record(solver_dir)
    assert len(rows) == 6
    for row in rows:
        result = compare(
            c, mode=row["mode"], frequency_GHz=row["f"], p_default=row["p_default"],
            p_ma=row["p_ma"], E_elec=row["E_elec"], E_mag=row["E_mag"],
            E_cap=row["E_cap"], E_ind=row["E_ind"],
        )
        assert result.probe_versus_closure == pytest.approx(1.0, rel=2e-5), (
            f"mode {row['mode']}: probe {result.participation_from_probes:.9e} vs "
            f"closure {result.participation_from_closure:.9e}"
        )


def test_the_probe_evaluation_does_not_depend_on_the_energy_balance():
    """Independence is asserted, not asserted-about.

    Perturbing ``E_mag`` moves the closure number and must not move the probe
    number. That is what makes their agreement evidence rather than tautology.
    """
    c = conversion()
    row = _record(L3)[0]
    kwargs = dict(
        mode=row["mode"], frequency_GHz=row["f"], p_default=row["p_default"],
        p_ma=row["p_ma"], E_elec=row["E_elec"], E_cap=row["E_cap"], E_ind=row["E_ind"],
    )
    a = compare(c, E_mag=row["E_mag"], **kwargs)
    b = compare(c, E_mag=row["E_mag"] * 3.0, **kwargs)
    assert b.participation_from_probes == a.participation_from_probes
    assert b.participation_from_closure != a.participation_from_closure


def test_closure_is_labelled_as_not_independent():
    """A port energy inferred from closure may not be quoted as verifying it."""
    c = conversion()
    row = _record(L3)[0]
    payload = compare(
        c, mode=row["mode"], frequency_GHz=row["f"], p_default=row["p_default"],
        p_ma=row["p_ma"], E_elec=row["E_elec"], E_mag=row["E_mag"],
        E_cap=row["E_cap"], E_ind=row["E_ind"],
    ).as_dict()
    assert payload["independence"]["from_closure"].startswith("NOT independent")
    assert "independent of the energy balance" in payload["independence"]["from_probes"]


def test_the_reported_surrogate_understates_the_port_energy_on_the_record():
    """Every committed mode has ``E_ind <= E_port``, as Cauchy-Schwarz requires."""
    c = conversion()
    for solver_dir in (L2, L3):
        for row in _record(solver_dir):
            result = compare(
                c, mode=row["mode"], frequency_GHz=row["f"], p_default=row["p_default"],
                p_ma=row["p_ma"], E_elec=row["E_elec"], E_mag=row["E_mag"],
                E_cap=row["E_cap"], E_ind=row["E_ind"],
            )
            assert result.uniformity_factor <= 1.0 + 1e-9, (solver_dir.parts[-2], row["mode"])


def test_the_two_in_window_L3_modes_have_near_uniform_port_fields():
    """The admitted in-window modes are the ones ``E_ind`` describes well.

    m1 and m2 have uniformity factors within 0.1 % of 1; the higher modes do
    not, which is what a rank-one surrogate failing looks like.
    """
    c = conversion()
    rows = {r["mode"]: r for r in _record(L3)}
    for mode in (1, 2):
        row = rows[mode]
        result = compare(
            c, mode=mode, frequency_GHz=row["f"], p_default=row["p_default"],
            p_ma=row["p_ma"], E_elec=row["E_elec"], E_mag=row["E_mag"],
            E_cap=row["E_cap"], E_ind=row["E_ind"],
        )
        assert result.uniformity_factor == pytest.approx(1.0, rel=1.0e-3), mode
    row = rows[6]
    out_of_window = compare(
        c, mode=6, frequency_GHz=row["f"], p_default=row["p_default"], p_ma=row["p_ma"],
        E_elec=row["E_elec"], E_mag=row["E_mag"], E_cap=row["E_cap"], E_ind=row["E_ind"],
    )
    assert out_of_window.uniformity_factor < 0.1


def test_the_EPR_column_is_the_reported_participation_up_to_sign():
    """``port-EPR.csv`` and ``E_ind/(E_elec+E_cap)`` are the same number.

    The EPR carries ``sign(Re I)``, which is a gauge choice, so the comparison
    is on magnitudes -- the convention this record uses throughout.
    """
    c = conversion()
    for row in _record(L3):
        result = compare(
            c, mode=row["mode"], frequency_GHz=row["f"], p_default=row["p_default"],
            p_ma=row["p_ma"], E_elec=row["E_elec"], E_mag=row["E_mag"],
            E_cap=row["E_cap"], E_ind=row["E_ind"],
        )
        assert abs(result.participation_reported) == pytest.approx(abs(row["p_epr"]), rel=1e-6)


def test_the_admission_rule_is_unchanged_but_now_says_what_it_selects():
    """The note is added; the quantity, the threshold and the behaviour are not.

    Pinning the numeric behaviour here means the documentation correction
    cannot drift into a tolerance change without this failing.
    """
    from solvers.palace.mode_admission import ADMISSION_RULE

    assert ADMISSION_RULE["id"] == "qmhp-cem.mode-admission/0.1.0"
    assert ADMISSION_RULE["max_energy_balance_defect"] == 1.0e-3
    assert ADMISSION_RULE["admit_when"] == "abs(R - 1) <= 1e-3"
    assert ADMISSION_RULE["quantity"].startswith("R = (E_mag + E_ind) / (E_elec + E_cap)")
    note = ADMISSION_RULE["what_that_means_for_this_rule"]
    assert "unchanged" in note
    assert "uniform and aligned" in note
    assert "COUPLED-S1-RECOVERY" in ADMISSION_RULE["what_the_missing_integral_turned_out_to_be"]


def test_the_admission_rule_still_admits_and_rejects_exactly_what_it_did():
    """The committed split is the behavioural pin: 2 in-window admitted at L3."""
    from solvers.palace.mode_admission import ModeRecord, admit_modes

    report = admit_modes(
        "L3",
        [
            ModeRecord(
                mode=r["mode"],
                frequency_GHz=r["f"],
                frequency_im_GHz=0.0,
                backward_error=0.0,
                absolute_error=None,
                electric_J=r["E_elec"],
                magnetic_J=r["E_mag"],
                capacitive_J=r["E_cap"],
                inductive_J=r["E_ind"],
                participation={1: r["p_epr"]},
                current_A={},
                voltage_V={},
            )
            for r in _record(L3)
        ],
        backward_error_tolerance=1.0e-6,
    )
    assert sorted(m.mode for m in report.admitted) == [1, 2, 6]
    assert sorted(m.record.mode for m in report.rejected) == [3, 4, 5]
