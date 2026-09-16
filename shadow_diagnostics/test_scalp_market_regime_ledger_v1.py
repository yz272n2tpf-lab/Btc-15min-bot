import unittest
from unittest.mock import patch

import scalp_market_regime_ledger_v1 as reg


class MarketRegimeLedgerV1Tests(unittest.TestCase):
    def base(self, **kw):
        r = {
            "structure_ok": 1,
            "btc_brti_agree5": 1,
            "btc_brti_agree15": 1,
            "btc_against_side": 0,
            "brti_against_side": 0,
            "dual_reversal_evidence": 0,
            "btc_move5_norm": .70,
            "btc_move15_norm": .60,
            "acceleration": 1.0,
            "ask_move15": .01,
        }
        r.update(kw)
        return r

    def test_trend_lag_and_acceleration_can_overlap(self):
        tags = reg.regime_tags(self.base(btc_move5_norm=.80))
        self.assertIn("TREND_ALIGNED", tags)
        self.assertIn("KALSHI_LAG", tags)
        self.assertIn("ACCELERATION_BURST", tags)
        self.assertEqual(reg.primary_regime(tags), "KALSHI_LAG")

    def test_reversal_hazard_has_primary_priority(self):
        tags = reg.regime_tags(self.base(dual_reversal_evidence=1))
        self.assertIn("REVERSAL_HAZARD", tags)
        self.assertEqual(reg.primary_regime(tags), "REVERSAL_HAZARD")
        self.assertNotIn("TREND_ALIGNED", tags)

    def test_chop_requires_weak_norm_and_broken_agreement(self):
        tags = reg.regime_tags(self.base(btc_move5_norm=.2, btc_move15_norm=.3,
                                         btc_brti_agree15=0, acceleration=-1.0,
                                         ask_move15=.08))
        self.assertEqual(tags, ["CHOP_LOW_CONVICTION"])

    def test_outcome_fields_do_not_change_tags(self):
        a = self.base()
        b = dict(a, plus10=1, peak_gain=.50, protected_exit_gain=.20,
                 result="WIN", future_move=99)
        self.assertEqual(reg.regime_tags(a), reg.regime_tags(b))

    def test_validation_holdout_shift_is_descriptive(self):
        v = {"primary_regimes": {"TREND_ALIGNED": {"signals": 10, "plus10_rate": .8,
                                                      "protected_exit_rate": .7,
                                                      "ten_lot_taker_taker_avg_net_c": 4,
                                                      "avg_entry_ask_c": 40}}}
        h = {"primary_regimes": {"TREND_ALIGNED": {"signals": 8, "plus10_rate": .6,
                                                      "protected_exit_rate": .5,
                                                      "ten_lot_taker_taker_avg_net_c": 1,
                                                      "avg_entry_ask_c": 45}}}
        out = reg.validation_to_holdout_shift(v, h)["TREND_ALIGNED"]
        self.assertAlmostEqual(out["plus10_rate_delta_holdout_minus_validation"], -.2)
        self.assertEqual(out["ten_lot_avg_net_c_delta"], -3)
        self.assertTrue(out["descriptive_only"])

    def test_analyze_never_selects_or_promotes(self):
        with patch.object(reg, "build_tagged_records", return_value=([], {})):
            out = reg.analyze([])
        self.assertTrue(out["outcomes_never_define_tags"])
        self.assertTrue(out["no_threshold_selection"])
        self.assertTrue(out["no_signal_suppression_or_rescue"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])


if __name__ == "__main__":
    unittest.main()
