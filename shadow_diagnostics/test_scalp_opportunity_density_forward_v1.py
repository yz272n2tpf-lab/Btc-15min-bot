import unittest
from unittest.mock import patch

import scalp_opportunity_density_forward_v1 as m


class OpportunityDensityForwardV1Tests(unittest.TestCase):
    def op(self, contract, idx, ask, left, *, p5=1, p10=0, p20=0):
        return {
            "contract": contract,
            "candidate_id": f"{contract}-{idx}",
            "opportunity_index": idx,
            "entry_ask": ask,
            "seconds_left": left,
            "timestamp": f"2026-09-16T12:{idx:02d}:00Z",
            "plus5": p5,
            "plus10": p10,
            "plus20": p20,
        }

    def fixture(self):
        contracts = {"ZERO", "ONE", "TWO", "FOUR"}
        opps = [
            self.op("ONE", 1, .30, 800, p10=1, p20=1),
            self.op("TWO", 1, .55, 600, p10=1),
            self.op("TWO", 2, .45, 300),
            self.op("FOUR", 1, .27, 700, p10=1),
            self.op("FOUR", 2, .40, 500, p10=1),
            self.op("FOUR", 3, .65, 250),
            self.op("FOUR", 4, .20, 150, p10=1, p20=1),
        ]
        return contracts, opps

    def test_quiet_contract_stays_in_true_denominator(self):
        contracts, opps = self.fixture()
        out = m.analyze_density(opps, contracts)
        self.assertEqual(out["true_contract_denominator"], 4)
        self.assertEqual(out["covered_contracts"], 3)
        self.assertEqual(out["true_contract_coverage"], .75)
        self.assertEqual(out["zero_opportunity_contracts"], 1)
        self.assertEqual(out["zero_opportunity_rate"], .25)
        self.assertEqual(out["opportunity_count_distribution"], {
            "0": 1, "1": 1, "2": 1, "3": 0, "4_PLUS": 1,
        })

    def test_multi_opportunity_density_is_contract_based(self):
        contracts, opps = self.fixture()
        out = m.analyze_density(opps, contracts)
        self.assertEqual(out["multi_opportunity_contract_counts"]["AT_LEAST_1"], 3)
        self.assertEqual(out["multi_opportunity_contract_counts"]["AT_LEAST_2"], 2)
        self.assertEqual(out["multi_opportunity_contract_counts"]["AT_LEAST_3"], 1)
        self.assertEqual(out["multi_opportunity_contract_counts"]["AT_LEAST_4"], 1)
        self.assertEqual(out["multi_opportunity_true_contract_coverage"]["AT_LEAST_2"], .5)
        self.assertEqual(out["avg_opportunities_per_full_contract"], 7 / 4)
        self.assertEqual(out["avg_opportunities_per_covered_contract"], 7 / 3)
        self.assertEqual(out["max_opportunity_index"], 4)

    def test_entry_economics_coverage_kept_separate(self):
        contracts, opps = self.fixture()
        out = m.analyze_density(opps, contracts)
        # ONE, TWO (second signal), FOUR have <=50c opportunities.
        self.assertEqual(out["affordable_contracts_le50"], 3)
        self.assertEqual(out["affordable_true_contract_coverage_le50"], .75)
        # ONE 30c and FOUR 27c hit the ideal 25-35c band.
        self.assertEqual(out["ideal_contracts_25_35"], 2)
        self.assertEqual(out["ideal_true_contract_coverage_25_35"], .5)
        self.assertEqual(out["ideal_opportunities_25_35"], 2)

    def test_timing_zone_boundaries_are_frozen(self):
        self.assertEqual(m.opportunity_zone(900), "15_TO_12M")
        self.assertEqual(m.opportunity_zone(720), "15_TO_12M")
        self.assertEqual(m.opportunity_zone(719.999), "12_TO_9M")
        self.assertEqual(m.opportunity_zone(540), "12_TO_9M")
        self.assertEqual(m.opportunity_zone(539.999), "9_TO_6M")
        self.assertEqual(m.opportunity_zone(360), "9_TO_6M")
        self.assertEqual(m.opportunity_zone(359.999), "6_TO_3M")
        self.assertEqual(m.opportunity_zone(180), "6_TO_3M")
        self.assertEqual(m.opportunity_zone(179.999), "3_TO_2M")
        self.assertEqual(m.opportunity_zone(120), "3_TO_2M")
        self.assertEqual(m.opportunity_zone(119.999), "OUTSIDE_15_TO_2M")

    def test_cumulative_deadlines_do_not_double_count_contracts(self):
        contracts, opps = self.fixture()
        out = m.analyze_density(opps, contracts)
        # By 12m left: only ONE has an opportunity at >=720 seconds left.
        self.assertEqual(out["cumulative_timing"]["BY_12M_LEFT"]["contracts_with_any_opportunity_by_deadline"], 1)
        # By 9m left: ONE, TWO and FOUR have appeared.
        self.assertEqual(out["cumulative_timing"]["BY_9M_LEFT"]["contracts_with_any_opportunity_by_deadline"], 3)
        self.assertEqual(out["cumulative_timing"]["BY_9M_LEFT"]["true_contract_coverage"], .75)

    def test_analyze_filters_out_non_denominator_opportunities(self):
        contracts = {"FUTURE_QUIET", "FUTURE_ACTIVE"}
        active = self.op("FUTURE_ACTIVE", 1, .42, 700, p10=1)
        old = self.op("OLD_OR_PARTIAL", 1, .25, 850, p10=1)
        with patch.object(m.econ_forward, "future_universe", return_value=(contracts, [])), \
             patch.object(m.q, "build_serial_opportunities", return_value=[active, old]):
            out = m.analyze_rows([], cutoff_text="2026-09-16T12:00:00Z")
        self.assertTrue(out["ok"])
        self.assertEqual(out["future_full_contracts"], 2)
        self.assertEqual(out["density"]["total_serial_opportunities"], 1)
        self.assertEqual(out["density"]["covered_contracts"], 1)
        self.assertEqual(out["density"]["zero_opportunity_contracts"], 1)
        self.assertEqual(out["density"]["true_contract_coverage"], .5)
        self.assertFalse(out["signal_filtering"])
        self.assertFalse(out["signal_suppression"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])

    def test_invalid_cutoff_fails_closed(self):
        out = m.analyze_rows([], cutoff_text="bad")
        self.assertFalse(out["ok"])
        self.assertEqual(out["status"], "FAIL_CLOSED_MISSING_OR_INVALID_CUTOFF")
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])

    def test_integrity_and_frozen_rules(self):
        m.assert_integrity()
        rules = m.frozen_rules()
        self.assertTrue(rules["quiet_contracts_count_as_zero_opportunity"])
        self.assertTrue(rules["serial_lifecycle_unchanged"])
        self.assertEqual(rules["entry_affordable_max_c"], 50.0)
        self.assertEqual(rules["entry_ideal_band_c"], [25.0, 35.0])
        self.assertFalse(rules["automatic_promotion"])
        self.assertFalse(rules["orders"])


if __name__ == "__main__":
    unittest.main()
