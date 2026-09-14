"""Unit tests for tools/v2a/check_assessment_arithmetic.py (stdlib unittest).

Standard library only. This directory also holds the CEM suite, which does need
the locked environment, so an unfiltered discover would try to import it too.

Run with:  python3 -m unittest discover -s tests -p 'test_assessment_arithmetic.py' -v
Or all suites together, in the locked environment:  uv run pytest
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "v2a"))

import check_assessment_arithmetic as m  # noqa: E402


class TestAllStatedValuesReproduce(unittest.TestCase):
    def test_every_stated_value_is_reproduced(self):
        failures = [c for c in m.checks if not c.ok]
        self.assertEqual(failures, [], msg="\n".join(
            f"{c.name}: stated {c.stated} computed {c.computed}" for c in failures))

    def test_squid_sign_spectral_equivalence(self):
        self.assertTrue(m.SQUID_OK)


class TestM1Timing(unittest.TestCase):
    def test_t_pi_formula(self):
        self.assertAlmostEqual(m.t_pi_from_zeta(62.1e3) * 1e6, 8.0515, places=3)

    def test_one_microsecond_requires_500khz(self):
        self.assertAlmostEqual(m.zeta_from_t_pi(1e-6), 500e3)

    def test_wait_range_maps_to_zeta_range(self):
        lo, hi = m.extras["M1_zeta_range_kHz_for_8.05_8.37_us"]
        self.assertAlmostEqual(lo, 62.11, places=2)
        self.assertAlmostEqual(hi, 59.74, places=2)


class TestDriveConvention(unittest.TestCase):
    def test_convention_A_reproduces_assessment_5p13_MHz(self):
        self.assertAlmostEqual(m.u_c_for_cycle(150e-9, m.N_C, "A") / 1e6, 5.126, places=2)

    def test_convention_B_is_half(self):
        a = m.u_c_for_cycle(150e-9, m.N_C, "A")
        b = m.u_c_for_cycle(150e-9, m.N_C, "B")
        self.assertAlmostEqual(a / b, 2.0)

    def test_150ns_cap_status_depends_on_convention(self):
        self.assertFalse(m.extras["150ns_inside_cap_convention_A"])
        self.assertTrue(m.extras["150ns_inside_cap_convention_B"])

    def test_all_other_durations_inside_cap_under_both_conventions(self):
        for row in m.extras["u_C_table"]:
            if row["T_ns"] != 150:
                self.assertTrue(row["within_5MHz_cap_A"], row)
                self.assertTrue(row["within_5MHz_cap_B"], row)

    def test_minimum_duration_at_cap(self):
        self.assertAlmostEqual(m.extras["T_min_ns_at_cap_convention_A"], 153.79, places=1)
        self.assertAlmostEqual(m.extras["T_min_ns_at_cap_convention_B"], 76.90, places=1)

    def test_envelope_peak_multipliers(self):
        self.assertAlmostEqual(m.extras["envelope_peak_multiplier_hann"], 2.0)
        self.assertGreater(m.extras["envelope_peak_multiplier_gaussian_2sigma"], 1.0)


class TestEnvelopeAndCapConsequences(unittest.TestCase):
    """Consequences the assessment states only qualitatively."""

    def test_crossover_matrix_element_is_four_thirds(self):
        self.assertAlmostEqual(m.N_C_CROSSOVER_A, 4.0 / 3.0)
        self.assertLess(m.N_C, m.N_C_CROSSOVER_A)      # 1.300454 -> outside the cap
        self.assertGreater(m.N_C_ALT, m.N_C_CROSSOVER_A)  # 1.36 -> inside

    def test_rectangular_breach_is_150ns_only(self):
        self.assertEqual(m.extras["durations_breaching_cap"]["rectangular/A"], [150])
        self.assertEqual(m.extras["durations_breaching_cap"]["rectangular/B"], [])

    def test_hann_breach_extends_beyond_150ns_under_convention_A(self):
        self.assertEqual(m.extras["durations_breaching_cap"]["hann/A"], [150, 200, 300])

    def test_hann_penalty_cancels_the_convention_factor_at_150ns(self):
        """2/(2 T n) == 1/(T n): 150 ns breaches under a Hann envelope either way."""
        self.assertIn(150, m.extras["durations_breaching_cap"]["hann/B"])
        rect_a = m.u_c_for_cycle(150e-9, m.N_C, "A")
        hann_b = m.u_c_for_cycle(150e-9, m.N_C, "B") / m.hann_area_fraction()
        self.assertAlmostEqual(rect_a, hann_b)

    def test_clamping_at_the_cap_costs_more_than_the_screen(self):
        self.assertAlmostEqual(m.residual_after_clamped_pulse(150e-9, m.N_C, "A"), 5.99e-3, places=4)
        self.assertGreater(m.extras["clamped_150ns_residual_vs_screen"], 7.0)

    def test_in_phase_crosstalk_at_minus_40dB_exceeds_the_screen(self):
        self.assertGreater(m.residual_from_amplitude_error(1e-2), m.SCREEN_ERROR)
        self.assertAlmostEqual(m.residual_from_amplitude_error(1e-2), 9.866e-4, places=6)

    def test_zeta_carries_the_same_factor_of_two_hazard_as_u_C(self):
        t = m.extras["zeta_convention_T_pi_us"]
        self.assertAlmostEqual(t["H/h = zeta |22><22|  (assessment)"] / t["H/h = (J/2) Z Z"], 2.0)

    def test_m1_shortfall_is_a_range_not_a_single_factor(self):
        lo, hi = m.extras["M1_shortfall_factor_range"]
        self.assertAlmostEqual(lo, 8.05, places=2)
        self.assertAlmostEqual(hi, 8.37, places=2)

    def test_mhz_to_mrad_conversion_is_two_pi_not_two(self):
        self.assertAlmostEqual(m.extras["conversion_factors"]["MHz_to_Mrad_per_s"], 2 * math.pi)


class TestThermal(unittest.TestCase):
    def test_bose_values(self):
        self.assertAlmostEqual(m.bose_occupation(m.F22_HZ, 0.015) / 1.78e-10, 1.0, places=2)
        self.assertAlmostEqual(m.bose_occupation(m.F22_HZ, 0.020) / 4.88e-8, 1.0, places=2)
        self.assertAlmostEqual(m.bose_occupation(m.F22_HZ, 0.030) / 1.34e-5, 1.0, places=1)

    def test_effective_temperatures_exceed_sweep(self):
        t = m.extras["effective_temperature_mK_for_initial_population"]
        self.assertGreater(t["0.001"], 30.0)
        self.assertGreater(t["0.01"], t["0.001"])

    def test_two_level_population_matches_bose_at_low_T(self):
        for T in (0.015, 0.020, 0.030):
            nb = m.bose_occupation(m.F22_HZ, T)
            p1 = m.two_level_excited_population(m.F22_HZ, T)
            self.assertAlmostEqual(p1 / nb, 1.0, places=4)


class TestCrosstalk(unittest.TestCase):
    def test_amplitude_ratios(self):
        self.assertAlmostEqual(m.amplitude_ratio_from_db(-40), 1e-2)
        self.assertAlmostEqual(m.amplitude_ratio_from_db(-80), 1e-4)
        self.assertAlmostEqual(m.amplitude_ratio_from_db(-60), 1e-3)
        self.assertAlmostEqual(m.amplitude_ratio_from_db(-50), 10 ** -2.5)

    def test_power_misread_is_square(self):
        for db in m.CROSSTALK_DB:
            self.assertAlmostEqual(m.power_ratio_from_db(db), m.amplitude_ratio_from_db(db) ** 2)


class TestSchedule(unittest.TestCase):
    def test_degree_sequence_is_surface17(self):
        self.assertEqual(m.extras["surface17_degree_sequence"], m.PAIR_COUNTS)
        self.assertEqual(sum(m.PAIR_COUNTS), 24)

    def test_balanced_four_layer_colouring_is_conflict_free(self):
        layers = m.extras["one_valid_4x6_layer_colouring"]
        self.assertEqual([len(L) for L in layers], [6, 6, 6, 6])
        for L in layers:
            ancillas = [a for a, _ in L]
            datas = [q for _, q in L]
            self.assertEqual(len(set(ancillas)), len(ancillas))
            self.assertEqual(len(set(datas)), len(datas))
        all_edges = sorted(e for L in layers for e in L)
        expected = sorted((a, q) for a, s in enumerate(m.SURFACE17_STABILISERS) for q in s)
        self.assertEqual(all_edges, expected)

    def test_three_layers_impossible(self):
        self.assertIsNone(m.edge_colouring(m.SURFACE17_STABILISERS, 3))


class TestScheduleInference(unittest.TestCase):
    """The sum of pair counts is necessary, not sufficient, for four layers."""

    def test_counterexample_shares_degrees_and_edge_count_but_needs_five_colours(self):
        self.assertEqual(m.ce_degrees, m.PAIR_COUNTS)
        self.assertEqual(m.ce_edges, 24)
        self.assertIsNone(m.edge_colouring(m.COUNTEREXAMPLE_STABILISERS, 4))
        self.assertIsNotNone(m.edge_colouring(m.COUNTEREXAMPLE_STABILISERS, 5))

    def test_surface17_four_colourability_comes_from_max_degree_four(self):
        self.assertEqual(max(m.extras["ancilla_degrees"]), 4)
        self.assertEqual(m.extras["ancilla_degrees"], [4, 4, 4, 4, 2, 2, 2, 2])

    def test_balanced_colouring_count(self):
        self.assertEqual(m.extras["balanced_4x6_colouring_count"], 481776)

    def test_hook_fatal_fraction(self):
        self.assertAlmostEqual(m.extras["hook_fatal_fraction"], 1.0 / 3.0)


class TestLedgerVariants(unittest.TestCase):
    def test_degree_resolved_duty_factor_is_13_over_15(self):
        d = m.extras["outside_fraction_by_accounting"]
        self.assertAlmostEqual(d["per_data_qubit_mean"], 13.0 / 15.0)
        self.assertEqual(d["per_data_qubit_mean_exact"], "13/15")
        self.assertAlmostEqual(d["per_ancilla_mean"], 0.85)
        self.assertAlmostEqual(d["all_17_qubits_mean"], 1.0 - 48.0 / 340.0)

    def test_uniform_0p8_is_the_lowest_of_every_accounting(self):
        d = m.extras["outside_fraction_by_accounting"]
        self.assertEqual(min(d[k] for k in d if k != "per_data_qubit_mean_exact"), d["wall_clock_uniform"])

    def test_background_term_shifts_by_8_percent(self):
        self.assertAlmostEqual(m.extras["background_relative_difference_percent"], 100.0 / 12.0)

    def test_one_over_f_exponent_changes_dephasing_residual_by_a_quarter(self):
        r = m.extras["dephasing_residual_by_exponent"]
        self.assertAlmostEqual(r["exponent 2 (1/f)"] / r["exponent 1 (as quoted)"], 0.8)

    def test_diagnostic_average_denominators(self):
        d = m.extras["diagnostic_average_by_denominator"]
        self.assertAlmostEqual(d["per data qubit (9)"], 2.1333e-3, places=6)
        self.assertAlmostEqual(d["per Surface-17 qubit (17)"], 24 * 8e-4 / 17)
        self.assertAlmostEqual(d["worst data qubit (degree 4)"] / d["best data qubit (degree 2)"], 2.0)

    def test_layer_budget_tension(self):
        t = m.extras["layer_budget_tension"]
        self.assertAlmostEqual(t["ratio"], 4.0 / (4 * 0.196773))


class TestLedger(unittest.TestCase):
    def test_diagnostic_average(self):
        self.assertAlmostEqual(24 * 8e-4 / 9, 2.1333e-3, places=6)

    def test_time_fraction(self):
        self.assertAlmostEqual((20.0 - 4 * 1.0) / 20.0, 0.8)

    def test_background_scaling(self):
        self.assertAlmostEqual(1.700e-3 * 0.8, 1.360e-3)
        self.assertAlmostEqual(1.441e-3 / 0.8, 1.80125e-3)


if __name__ == "__main__":
    unittest.main()
