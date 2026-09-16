import unittest
from unittest.mock import patch

import scalp_market_regime_ledger_v1 as v1
import scalp_market_regime_ledger_v1_1 as v11


class MarketRegimeLedgerV11Tests(unittest.TestCase):
    def base(self, **kw):
        r = {
            "structure_ok": 1.0,
            "btc_brti_agree5": 1.0,
            "btc_brti_agree15": 1.0,
            "btc_against_side": 0.0,
            "brti_against_side": 0.0,
            "dual_reversal_evidence": 0.0,
            "btc_move5_norm": .80,
            "btc_move15_norm": .60,
            "acceleration": 2.0,
            "ask_move15": .01,
        }
        r.update(kw)
        return r

    def test_numeric_float_boolean_semantic_repair(self):
        self.assertFalse(v1.truthy(1.0))
        self.assertTrue(v11.truthy(1.0))
        self.assertFalse(v11.truthy(0.0))
        self.assertTrue(v11.truthy("1.0"))
        self.assertTrue(v11.truthy("true"))

    def test_same_thresholds_now_allow_expected_trend_lag_and_accel_tags(self):
        tags = v11.regime_tags(self.base())
        self.assertIn("TREND_ALIGNED", tags)
        self.assertIn("KALSHI_LAG", tags)
        self.assertIn("ACCELERATION_BURST", tags)
        self.assertEqual(v11.primary_regime(tags), "KALSHI_LAG")

    def test_numeric_true_reversal_flag_is_now_recognized(self):
        tags = v11.regime_tags(self.base(dual_reversal_evidence=1.0))
        self.assertIn("REVERSAL_HAZARD", tags)
        self.assertNotIn("TREND_ALIGNED", tags)
        self.assertEqual(v11.primary_regime(tags), "REVERSAL_HAZARD")

    def test_thresholds_are_identical_to_v1(self):
        self.assertEqual(v1.TREND_BTC5_NORM_MIN, .60)
        self.assertEqual(v1.TREND_BTC15_NORM_MIN, .50)
        self.assertEqual(v1.ACCEL_BTC5_NORM_MIN, .75)
        self.assertEqual(v1.CHOP_BTC5_NORM_MAX, .45)
        self.assertEqual(v1.CHOP_BTC15_NORM_MAX, .45)
        self.assertEqual(v1.KALSHI_LAG_ABS_ASK15_MAX, .02)
        v11.assert_integrity()

    def test_outcomes_do_not_change_repaired_tags(self):
        a = self.base()
        b = dict(a, plus10=1, peak_gain=.99, protected_exit_gain=.4,
                 result="WIN", future_move=999)
        self.assertEqual(v11.regime_tags(a), v11.regime_tags(b))

    def test_analyze_is_descriptive_no_promotion(self):
        with patch.object(v11, "build_tagged_records", return_value=([], {})):
            out = v11.analyze([])
        self.assertTrue(out["semantic_repair"]["numeric_float_boolean_flags_recognized"])
        self.assertFalse(out["semantic_repair"]["thresholds_changed"])
        self.assertTrue(out["holdout_is_descriptive_after_semantic_repair"])
        self.assertTrue(out["holdout_cannot_select_v1_1_rule"])
        self.assertTrue(out["no_threshold_selection"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])


if __name__ == "__main__":
    unittest.main()
