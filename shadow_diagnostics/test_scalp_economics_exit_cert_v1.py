import unittest
from unittest.mock import patch

import scalp_economics_exit_cert_v1 as econ


class ScalpEconomicsExitCertTests(unittest.TestCase):
    def test_taker_fee_rounding_depends_on_lot_size(self):
        self.assertAlmostEqual(econ.kalshi_fee_total(0.50, 1), 0.02)
        self.assertAlmostEqual(econ.kalshi_fee_total(0.50, 100), 1.75)
        one = econ.fee_adjusted_per_contract(0.50, 0.60, 1)
        hundred = econ.fee_adjusted_per_contract(0.50, 0.60, 100)
        self.assertGreater(one["round_trip_fee_dollars_per_contract"],
                           hundred["round_trip_fee_dollars_per_contract"])

    def test_default_maker_entry_has_zero_general_maker_fee(self):
        x = econ.fee_adjusted_per_contract(0.40, 0.50, 10, entry_maker=True)
        self.assertAlmostEqual(x["entry_fee_total_dollars"], 0.0)
        self.assertGreater(x["exit_fee_total_dollars"], 0.0)

    def test_plus10_touch_is_not_realized_plus10(self):
        op = {
            "contract": "C1", "candidate_id": "A", "opportunity_index": 1,
            "side": "UP", "entry_ask": 0.40, "seconds_left": 600,
            "plus5": 1, "plus10": 1, "plus20": 0,
            "peak_gain": 0.12, "adverse_gain": -0.01,
            "protected_exit_gain": 0.03,
        }
        rec = econ._op_record(op)
        self.assertEqual(rec["gross_protected_gain_c"], 3.0)
        self.assertEqual(rec["plus10"], 1)
        self.assertNotEqual(rec["gross_protected_gain_c"], 10.0)

    def test_unprotected_path_has_no_realized_fee_adjusted_result(self):
        op = {
            "contract": "C1", "candidate_id": "A", "opportunity_index": 1,
            "side": "UP", "entry_ask": 0.30, "seconds_left": 600,
            "plus5": 1, "plus10": 1, "plus20": 0,
            "peak_gain": 0.11, "adverse_gain": -0.02,
            "protected_exit_gain": None,
        }
        rec = econ._op_record(op)
        self.assertFalse(rec["protected_exit_observed"])
        self.assertIsNone(rec["gross_protected_gain_c"])
        self.assertEqual(rec["fee_scenarios"], {})
        s = econ.summarize([rec])
        self.assertEqual(s["protected_exit_signals"], 0)
        self.assertEqual(s["unprotected_signals_not_counted_as_realized"], 1)

    def test_analyze_keeps_opportunity_indices_separate(self):
        ops = [
            {"contract": "C1", "candidate_id": "A", "opportunity_index": 1,
             "side": "UP", "entry_ask": .40, "seconds_left": 700,
             "plus5": 1, "plus10": 1, "plus20": 0,
             "peak_gain": .12, "adverse_gain": -.01, "protected_exit_gain": .06},
            {"contract": "C1", "candidate_id": "B", "opportunity_index": 2,
             "side": "DOWN", "entry_ask": .35, "seconds_left": 400,
             "plus5": 1, "plus10": 0, "plus20": 0,
             "peak_gain": .07, "adverse_gain": -.02, "protected_exit_gain": .02},
            {"contract": "C2", "candidate_id": "C", "opportunity_index": 4,
             "side": "UP", "entry_ask": .25, "seconds_left": 180,
             "plus5": 1, "plus10": 1, "plus20": 1,
             "peak_gain": .21, "adverse_gain": -.01, "protected_exit_gain": .10},
        ]
        with patch.object(econ.q, "build_serial_opportunities", return_value=ops):
            r = econ.analyze([])
        self.assertEqual(set(r["by_opportunity_index"]), {"1", "2", "4"})
        self.assertEqual(r["by_opportunity_index"]["2"]["signals"], 1)
        self.assertEqual(r["overall"]["max_opportunity_index"], 4)

    def test_integrity_keeps_legacy_lifecycle_and_no_orders(self):
        econ.assert_integrity()
        with patch.object(econ.q, "build_serial_opportunities", return_value=[]):
            r = econ.analyze([])
        self.assertFalse(r["orders"])
        self.assertFalse(r["automatic_promotion"])
        self.assertFalse(r["production_logic_changed"])
        self.assertIn("not treated as realized", r["movement_vs_realized_warning"])


if __name__ == "__main__":
    unittest.main()
