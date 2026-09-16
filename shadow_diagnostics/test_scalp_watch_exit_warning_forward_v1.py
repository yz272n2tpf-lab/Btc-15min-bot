import unittest
from unittest.mock import patch

import scalp_watch_exit_warning_forward_v1 as m


class WatchExitWarningForwardV1Tests(unittest.TestCase):
    def op(self, contract="C1", gains=None):
        gains = gains or [(1.0, .02), (2.0, .06), (3.0, .04), (4.0, .07), (5.0, .02)]
        return {
            "contract": contract,
            "candidate_id": contract + "-1",
            "opportunity_index": 1,
            "entry_ask": .40,
            "seconds_left": 600.0,
            "_candidate": {"timestamp_utc": "2026-09-16T12:00:00Z"},
            "_paths": [{"elapsed_sec": e, "exec_gain": g} for e, g in gains],
            "plus5": 1,
            "plus10": 0,
            "plus20": 0,
            "peak_gain": max(g for _, g in gains),
            "adverse_gain": min(g for _, g in gains),
            "protected_exit_gain": None,
        }

    def test_watch_never_triggers_before_arm(self):
        op = self.op(gains=[(1, .01), (2, -.03), (3, .02), (4, .049)])
        z = m.measure_watch_exit(op, .01)
        self.assertFalse(z["armed"])
        self.assertFalse(z["watch_triggered"])
        self.assertFalse(z["exit_observed"])

    def test_watch_can_recover_then_frozen_exit_later(self):
        # Arm at +6c, Watch 1c lane at +4c, recover to a new +7c high,
        # then frozen Exit at +2c after a 5c giveback from that new high.
        op = self.op(gains=[(1, .06), (2, .04), (3, .07), (4, .02)])
        z = m.measure_watch_exit(op, .01)
        self.assertTrue(z["armed"])
        self.assertTrue(z["watch_triggered"])
        self.assertEqual(z["watch_time_sec"], 2.0)
        self.assertTrue(z["recovered_new_high_after_watch"])
        self.assertTrue(z["exit_observed"])
        self.assertEqual(z["exit_time_sec"], 4.0)
        self.assertAlmostEqual(z["watch_to_exit_lead_sec"], 2.0)
        self.assertAlmostEqual(z["exit_gain_c"], 2.0)

    def test_warning_without_exit_is_reported_not_fabricated(self):
        op = self.op(gains=[(1, .06), (2, .039), (3, .05), (4, .055)])
        z = m.measure_watch_exit(op, .02)
        self.assertTrue(z["watch_triggered"])
        self.assertFalse(z["exit_observed"])
        self.assertTrue(z["warning_without_exit"])
        self.assertIsNone(z["watch_to_exit_lead_sec"])

    def test_four_cent_exit_matches_legacy_path_measurement(self):
        op = self.op(gains=[(1, .06), (2, .055), (3, .08), (4, .05), (5, .039)])
        z = m.measure_watch_exit(op, .02)
        self.assertTrue(z["watch_triggered"])
        self.assertTrue(z["exit_observed"])
        self.assertEqual(z["exit_time_sec"], 5.0)
        self.assertAlmostEqual(z["exit_gain_c"], 3.9)

    def test_fixed_rules_and_integrity(self):
        m.assert_integrity()
        rules = m.frozen_rules()
        self.assertEqual(rules["arm_gain_c"], 5.0)
        self.assertEqual(rules["watch_giveback_candidates_c"], [1.0, 2.0, 3.0])
        self.assertEqual(rules["exit_giveback_c"], 4.0)
        self.assertFalse(rules["watch_policy_selection"])
        self.assertFalse(rules["same_sample_promotion"])
        self.assertFalse(rules["automatic_promotion"])
        self.assertFalse(rules["orders"])

    def test_analyze_restricts_to_future_full_contracts_and_no_promotion(self):
        old = self.op("OLD")
        fut = self.op("FUT")
        with patch.object(m.econ_forward, "future_universe", return_value=({"FUT"}, [])), \
             patch.object(m.q, "build_serial_opportunities", return_value=[old, fut]), \
             patch.object(m.econ, "_op_record", return_value={"fee_scenarios": {}}):
            out = m.analyze_rows([], cutoff_text="2026-09-16T12:00:00Z")
        self.assertTrue(out["ok"])
        self.assertEqual(out["future_full_contracts"], 1)
        self.assertEqual(out["serial_signals"], 1)
        self.assertFalse(out["policy_selection"])
        self.assertFalse(out["same_sample_promotion"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])
        self.assertEqual(set(out["policies"]), {"WATCH_1C", "WATCH_2C", "WATCH_3C"})

    def test_invalid_cutoff_fails_closed(self):
        out = m.analyze_rows([], cutoff_text="not-a-time")
        self.assertFalse(out["ok"])
        self.assertEqual(out["status"], "FAIL_CLOSED_MISSING_OR_INVALID_CUTOFF")
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])


if __name__ == "__main__":
    unittest.main()
