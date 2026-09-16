import unittest
from unittest.mock import patch

import scalp_regime_tag_coverage_audit_v1 as v1
import scalp_regime_tag_coverage_audit_v1_1 as v11


class RegimeTagCoverageAuditV11Tests(unittest.TestCase):
    def base(self, **kw):
        r = {
            "contract": "C1", "candidate_id": "X1", "opportunity_index": 1,
            "side": "UP", "timestamp": "2026-09-16T10:00:00Z",
            "structure_ok": 1.0,
            "btc_brti_agree5": 1.0,
            "btc_brti_agree15": 1.0,
            "btc_against_side": 0.0,
            "brti_against_side": 0.0,
            "dual_reversal_evidence": 0.0,
            "brti_primary_ok": 1.0,
            "btc_move5_norm": .80,
            "btc_move15_norm": .60,
            "acceleration": 2.0,
            "ask_move15": .01,
            "btc_move5_side": 8.0,
            "btc_move15_side": 12.0,
            "brti_move5_side": 7.0,
            "brti_move15_side": 11.0,
            "split": "VALIDATION",
        }
        r.update(kw)
        return r

    def test_numeric_float_boolean_repair(self):
        self.assertFalse(v1.b(1.0))
        self.assertTrue(v11.b(1.0))
        self.assertFalse(v11.b(0.0))
        self.assertTrue(v11.b("1.0"))

    def test_repaired_flags_clear_trend_and_lag_blockers(self):
        row = self.base()
        self.assertEqual(v11.trend_blockers(row), [])
        self.assertEqual(v11.lag_blockers(row), [])
        flags = v11.condition_flags(row)
        self.assertTrue(flags["structure_ok"])
        self.assertTrue(flags["agree5"])
        self.assertTrue(flags["agree15"])
        self.assertTrue(flags["no_reversal_evidence"])

    def test_repaired_tag_counts_use_v11_semantics(self):
        out = v11.split_audit([self.base()])
        self.assertEqual(out["tag_counts"]["primary"].get("KALSHI_LAG"), 1)
        self.assertEqual(out["trend_funnel"]["final"], 1)
        self.assertEqual(out["kalshi_lag_funnel"]["final"], 1)
        self.assertEqual(out["acceleration_funnel"]["final"], 1)

    def test_causal_allow_list_is_identical_to_v1(self):
        self.assertEqual(v11.AUDIT_ALLOWED_KEYS, v1.AUDIT_ALLOWED_KEYS)
        self.assertFalse(any(k.startswith("_") for k in v11.AUDIT_ALLOWED_KEYS))
        self.assertFalse(any("plus10" in k.lower() for k in v11.AUDIT_ALLOWED_KEYS))
        v11.assert_integrity()

    def test_outcomes_cannot_change_audit_flags(self):
        a = self.base()
        b = dict(a, plus10=1, peak_gain=.99, protected_exit_gain=.40,
                 future_move=999, result="WIN", _paths=[{"gain": .99}])
        self.assertEqual(v11.condition_flags(a), v11.condition_flags(b))
        self.assertEqual(v11.trend_blockers(a), v11.trend_blockers(b))

    def test_analyze_remains_descriptive_only(self):
        with patch.object(v11, "build_causal_opportunities", return_value=([self.base()], {})):
            out = v11.analyze([])
        self.assertTrue(out["semantic_repair"]["numeric_float_boolean_flags_recognized"])
        self.assertFalse(out["semantic_repair"]["thresholds_changed"])
        self.assertTrue(out["holdout_cannot_select_v1_1_rule"])
        self.assertFalse(out["threshold_selection"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])


if __name__ == "__main__":
    unittest.main()
