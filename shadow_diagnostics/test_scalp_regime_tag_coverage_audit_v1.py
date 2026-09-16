import unittest
from unittest.mock import patch

import scalp_regime_tag_coverage_audit_v1 as audit


class RegimeTagCoverageAuditV1Tests(unittest.TestCase):
    def row(self, **kw):
        r = {
            "contract": "C1", "candidate_id": "A", "opportunity_index": 1,
            "structure_ok": 1, "btc_brti_agree5": 1, "btc_brti_agree15": 1,
            "btc_against_side": 0, "brti_against_side": 0,
            "dual_reversal_evidence": 0, "brti_primary_ok": 1,
            "btc_move5_norm": .70, "btc_move15_norm": .60,
            "acceleration": 1.0, "ask_move15": .01,
            "btc_move5_side": 10, "btc_move15_side": 12,
            "brti_move5_side": 8, "brti_move15_side": 9,
        }
        r.update(kw)
        return r

    def test_clean_records_use_explicit_allow_list_only(self):
        op = self.row(plus10=1, peak_gain=.25, protected_exit_gain=.08,
                      _candidate={"secret": 1}, _paths=[{"exec_gain": .1}])
        with patch.object(audit.adapter, "adapt_rows", return_value=[]), \
             patch.object(audit.q, "build_serial_opportunities", return_value=[op]), \
             patch.object(audit.q, "chronological_split", return_value={"C1": "VALIDATION"}):
            clean, _ = audit.build_causal_opportunities([])
        self.assertEqual(len(clean), 1)
        self.assertNotIn("plus10", clean[0])
        self.assertNotIn("peak_gain", clean[0])
        self.assertNotIn("protected_exit_gain", clean[0])
        self.assertNotIn("_candidate", clean[0])
        self.assertNotIn("_paths", clean[0])
        self.assertEqual(clean[0]["split"], "VALIDATION")
        self.assertTrue(set(clean[0]).issubset(audit.AUDIT_ALLOWED_KEYS | {"split"}))

    def test_trend_funnel_passes_complete_trend_row(self):
        out = audit.split_audit([self.row()])
        self.assertEqual(out["trend_funnel"]["final"], 1)
        self.assertEqual(out["kalshi_lag_funnel"]["final"], 1)
        self.assertEqual(out["trend_blockers"]["zero_blocker_count"], 1)

    def test_blockers_explain_sparse_trend(self):
        r = self.row(structure_ok=0, btc_brti_agree15=0,
                     btc_move5_norm=.20, btc_move15_norm=.10)
        blockers = audit.trend_blockers(r)
        self.assertIn("STRUCTURE_FALSE", blockers)
        self.assertIn("AGREE15_FALSE", blockers)
        self.assertIn("BTC5_NORM_BELOW_0_60", blockers)
        self.assertIn("BTC15_NORM_BELOW_0_50", blockers)

    def test_missing_numeric_is_separate_from_below_threshold(self):
        r = self.row(btc_move5_norm=None)
        blockers = audit.trend_blockers(r)
        self.assertIn("BTC5_NORM_MISSING", blockers)
        self.assertNotIn("BTC5_NORM_BELOW_0_60", blockers)
        s = audit.numeric_summary([r], "btc_move5_norm")
        self.assertEqual(s["missing"], 1)
        self.assertEqual(s["present"], 0)

    def test_reversal_evidence_is_candidate_time_only(self):
        r = self.row(btc_against_side=1)
        self.assertTrue(audit.reversal_evidence(r))
        self.assertIn("REVERSAL_EVIDENCE", audit.trend_blockers(r))
        out = audit.split_audit([r])
        self.assertEqual(out["reversal_evidence_count"], 1)

    def test_outcome_values_cannot_change_audit_result(self):
        a = self.row()
        b = dict(a, plus10=1, peak_gain=.99, protected_exit_gain=.40,
                 result="WIN", future_move=999, _paths=[{"exec_gain": .9}])
        # split_audit sees only causal fields by contract; outcome extras are
        # ignored by all condition and feature functions.
        self.assertEqual(audit.condition_flags(a), audit.condition_flags(b))
        self.assertEqual(audit.trend_blockers(a), audit.trend_blockers(b))
        self.assertEqual(audit.regime.regime_tags(a), audit.regime.regime_tags(b))

    def test_analyze_never_selects_or_promotes(self):
        with patch.object(audit, "build_causal_opportunities", return_value=([], {})):
            out = audit.analyze([])
        self.assertFalse(out["threshold_selection"])
        self.assertFalse(out["outcomes_used_for_blockers_or_distributions"])
        self.assertTrue(out["no_signal_suppression_or_rescue"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])


if __name__ == "__main__":
    unittest.main()
