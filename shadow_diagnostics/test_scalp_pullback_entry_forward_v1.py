import unittest
from unittest.mock import patch

import scalp_pullback_entry_forward_v1 as m


class PullbackEntryForwardV1Tests(unittest.TestCase):
    def op(self, contract="C1", ask=.60, left=600.0, paths=None, idx=1):
        paths = paths or []
        return {
            "contract": contract,
            "candidate_id": f"{contract}-{idx}",
            "opportunity_index": idx,
            "entry_ask": ask,
            "seconds_left": left,
            "_candidate": {"timestamp_utc": "2026-09-16T12:00:00Z"},
            "_paths": [dict(elapsed_sec=e, current_ask=a, current_bid=b) for e, a, b in paths],
            "plus5": 0,
            "plus10": 0,
            "plus20": 0,
            "peak_gain": None,
            "adverse_gain": None,
            "protected_exit_gain": None,
        }

    def test_first_actual_ask_at_target_is_entry(self):
        op = self.op(paths=[
            (5, .58, .57),
            (10, .49, .48),
            (15, .47, .55),
            (20, .46, .60),
        ])
        z = m.replay_from_pullback(op, .50, 30.0)
        self.assertIsNotNone(z)
        self.assertEqual(z["entry_elapsed_sec"], 10.0)
        self.assertEqual(z["entry_ask"], .49)
        self.assertAlmostEqual(z["entry_improvement_c_vs_candidate"], 11.0)
        self.assertTrue(z["post_candidate_price_improvement"])

    def test_pre_entry_favorable_bid_is_discarded(self):
        # +20c-looking BID at t=5 is BEFORE the <=50c entry at t=10 and must not count.
        op = self.op(paths=[
            (5, .59, .80),
            (10, .49, .48),
            (15, .50, .54),
            (20, .52, .58),
        ])
        z = m.replay_from_pullback(op, .50, 30.0)
        self.assertIsNotNone(z)
        self.assertEqual(z["entry_elapsed_sec"], 10.0)
        self.assertEqual(z["plus5"], 1)
        self.assertEqual(z["plus10"], 0)
        self.assertEqual(z["plus20"], 0)
        self.assertAlmostEqual(z["peak_gain"], .09)

    def test_candidate_already_under_target_qualifies_immediately(self):
        op = self.op(ask=.45, paths=[(5, .46, .50), (10, .48, .56)])
        z = m.replay_from_pullback(op, .50, 30.0)
        self.assertIsNotNone(z)
        self.assertEqual(z["entry_elapsed_sec"], 0.0)
        self.assertEqual(z["entry_ask"], .45)
        self.assertTrue(z["qualified_immediately"])
        self.assertFalse(z["post_candidate_price_improvement"])
        self.assertEqual(z["plus10"], 1)

    def test_no_target_hit_means_no_pullback_entry(self):
        op = self.op(paths=[(5, .58, .57), (20, .55, .54), (30, .51, .50), (40, .48, .47)])
        self.assertIsNone(m.replay_from_pullback(op, .50, 30.0))
        # The same path does qualify inside the longer frozen 60s window.
        z = m.replay_from_pullback(op, .50, 60.0)
        self.assertIsNotNone(z)
        self.assertEqual(z["entry_elapsed_sec"], 40.0)
        self.assertEqual(z["entry_ask"], .48)

    def test_protection_restarts_from_pullback_entry(self):
        # Enter 49c at t=10. Post-entry BIDs: 55 (+6), 58 (+9), 53 (+4).
        # +5 arm is reached, then 5c giveback from peak triggers frozen exit at +4.
        op = self.op(paths=[
            (5, .58, .70),  # ignored pre-entry
            (10, .49, .48),
            (15, .52, .55),
            (20, .55, .58),
            (25, .54, .53),
        ])
        z = m.replay_from_pullback(op, .50, 30.0)
        self.assertIsNotNone(z)
        self.assertTrue(z["protected_exit_observed"])
        self.assertAlmostEqual(z["protected_exit_gain"], .04)
        self.assertEqual(z["protected_exit_elapsed_sec"], 25.0)
        self.assertIsNotNone(z["one_lot_taker_taker_net_c"])
        self.assertIsNotNone(z["ten_lot_taker_taker_net_c"])

    def test_fixed_lane_set_and_no_same_sample_promotion(self):
        m.assert_integrity()
        rules = m.frozen_rules()
        self.assertEqual(rules["absolute_ask_targets_c"], [50.0, 40.0, 35.0])
        self.assertEqual(rules["wait_windows_sec"], [30.0, 60.0])
        self.assertTrue(rules["pre_entry_movement_is_discarded"])
        self.assertTrue(rules["protection_rebased_from_actual_pullback_entry"])
        self.assertFalse(rules["lane_selection"])
        self.assertFalse(rules["same_sample_promotion"])
        self.assertFalse(rules["automatic_promotion"])
        self.assertFalse(rules["orders"])

    def test_analyze_keeps_true_future_denominator_and_quiet_contract(self):
        active = self.op("ACTIVE", ask=.60, paths=[(10, .49, .48), (20, .50, .60)])
        old = self.op("OLD", ask=.30, paths=[(5, .29, .40)])
        contracts = {"ACTIVE", "QUIET"}
        with patch.object(m.econ_forward, "future_universe", return_value=(contracts, [])), \
             patch.object(m.q, "build_serial_opportunities", return_value=[active, old]), \
             patch.object(m.econ, "_op_record", return_value={"protected_exit_observed": False, "fee_scenarios": {}}):
            out = m.analyze_rows([], cutoff_text="2026-09-16T12:00:00Z")
        self.assertTrue(out["ok"])
        self.assertEqual(out["future_full_contracts"], 2)
        self.assertEqual(out["immediate"]["signals"], 1)
        self.assertEqual(out["immediate"]["contracts"], 1)
        self.assertEqual(out["immediate"]["true_future_contract_coverage"], .5)
        self.assertEqual(len(out["lanes"]), 6)
        self.assertIn("LE50C_WITHIN_30S", out["lanes"])
        self.assertFalse(out["lane_selection"])
        self.assertFalse(out["same_sample_promotion"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])

    def test_invalid_cutoff_fails_closed(self):
        out = m.analyze_rows([], cutoff_text="bad")
        self.assertFalse(out["ok"])
        self.assertEqual(out["status"], "FAIL_CLOSED_MISSING_OR_INVALID_CUTOFF")
        self.assertFalse(out["lane_selection"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])


if __name__ == "__main__":
    unittest.main()
