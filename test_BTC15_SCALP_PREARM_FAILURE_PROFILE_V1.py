#!/usr/bin/env python3
import unittest

import BTC15_SCALP_PREARM_FAILURE_PROFILE_V1 as m


class PrearmFailureProfileTests(unittest.TestCase):
    def test_profiles_groups_without_selecting_rule(self):
        rows = [
            {"group":"PLUS10_OR_BETTER","btc5":10,"btc15":20,"btc30":30,"brti5":4,"brti15":6,"accel":3,"btc5_norm":.5,"btc15_norm":.6,"recent_btc_range60":20,"confirm_count":3,"ask5":0,"ask15":0},
            {"group":"UNARMED_SUB5","btc5":6,"btc15":14,"btc30":18,"brti5":2,"brti15":3,"accel":1,"btc5_norm":.3,"btc15_norm":.4,"recent_btc_range60":22,"confirm_count":2,"ask5":.01,"ask15":.01},
            {"group":"ARMED_SUB10","btc5":8,"btc15":16,"btc30":22,"brti5":3,"brti15":4,"accel":2,"btc5_norm":.4,"btc15_norm":.5,"recent_btc_range60":21,"confirm_count":2,"ask5":.005,"ask15":.005},
        ]
        out=m.summarize_records(rows)
        self.assertEqual(out["group_counts"]["PLUS10_OR_BETTER"],1)
        self.assertEqual(out["group_counts"]["UNARMED_SUB5"],1)
        self.assertLess(out["field_profiles"]["btc5"]["unarmed_minus_plus10_median"],0)
        self.assertTrue(out["hypothesis_generation_only"])
        self.assertFalse(out["feature_selected"])
        self.assertFalse(out["threshold_selected"])
        self.assertTrue(out["new_future_holdout_required"])

    def test_price_and_time_are_not_profiled_fields(self):
        self.assertNotIn("entry_ask", m.FIELDS)
        self.assertNotIn("seconds_left", m.FIELDS)
        self.assertNotIn("current_bid", m.FIELDS)

    def test_safety_envelope(self):
        out=m.summarize_records([])
        self.assertFalse(out["orders"])
        self.assertTrue(out["manual_execution_only"])
        self.assertFalse(out["entry_price_filter_applied"])
        self.assertFalse(out["fixed_time_window_applied"])
        self.assertFalse(out["protected_thresholds_changed"])
        self.assertFalse(out["stop_loss_rule_selected"])
        self.assertFalse(out["auto_promote_allowed"])
        self.assertFalse(out["actionable_now"])


if __name__ == "__main__":
    unittest.main()
