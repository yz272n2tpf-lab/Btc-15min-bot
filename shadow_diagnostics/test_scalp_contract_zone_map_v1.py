#!/usr/bin/env python3
import unittest

import scalp_contract_zone_map_v1 as z


class ScalpContractZoneMapTests(unittest.TestCase):
    def test_zone_boundaries(self):
        self.assertEqual(z.zone_for(899), "15-12m")
        self.assertEqual(z.zone_for(720), "15-12m")
        self.assertEqual(z.zone_for(719.9), "12-9m")
        self.assertEqual(z.zone_for(540), "12-9m")
        self.assertEqual(z.zone_for(539.9), "9-6m")
        self.assertEqual(z.zone_for(360), "9-6m")
        self.assertEqual(z.zone_for(359.9), "6-3m")
        self.assertEqual(z.zone_for(180), "6-3m")
        self.assertEqual(z.zone_for(179.9), "3-2m")
        self.assertEqual(z.zone_for(120), "3-2m")
        self.assertEqual(z.zone_for(119.9), "UNDER_2M_OUTSIDE_BASELINE")

    def test_first_opportunity_uses_earliest_wall_clock(self):
        opps = [
            {"contract": "A", "seconds_left": 400},
            {"contract": "A", "seconds_left": 700},
            {"contract": "A", "seconds_left": 250},
        ]
        first = z.first_opportunity_by_contract(opps)
        self.assertEqual(first["A"]["seconds_left"], 700)

    def test_cumulative_coverage_keeps_quiet_contracts_in_denominator(self):
        opps = [
            {
                "contract": "A", "seconds_left": 800, "entry_ask": .40,
                "plus5": 1, "plus10": 1, "plus20": 0,
                "peak_gain": .12, "adverse_gain": -.01, "protected_exit_gain": .08, "t10_sec": 30,
            },
            {
                "contract": "B", "seconds_left": 600, "entry_ask": .60,
                "plus5": 1, "plus10": 1, "plus20": 0,
                "peak_gain": .11, "adverse_gain": -.02, "protected_exit_gain": .07, "t10_sec": 45,
            },
        ]
        rows = z.cumulative_map(opps, {"A", "B", "C", "D"})
        by_name = {r["checkpoint"]: r for r in rows}
        self.assertAlmostEqual(by_name["by_12m_left"]["true_contract_coverage"], .25)
        self.assertAlmostEqual(by_name["by_9m_left"]["true_contract_coverage"], .50)
        self.assertAlmostEqual(by_name["by_9m_left"]["affordable_true_contract_coverage_le50"], .25)

    def test_zone_map_does_not_drop_quiet_contracts(self):
        opps = [
            {
                "contract": "A", "seconds_left": 750, "entry_ask": .30,
                "plus5": 1, "plus10": 1, "plus20": 1,
                "peak_gain": .22, "adverse_gain": -.01, "protected_exit_gain": .10, "t10_sec": 20,
            },
        ]
        z.add_zone_tags(opps)
        rows = z.score_zone_map(opps, {"A", "B"})
        first_zone = next(r for r in rows if r["zone"] == "15-12m")
        self.assertEqual(first_zone["true_contract_denominator"], 2)
        self.assertAlmostEqual(first_zone["true_contract_coverage"], .50)
        self.assertAlmostEqual(first_zone["first_opportunity_contract_share"], .50)


if __name__ == "__main__":
    unittest.main()
