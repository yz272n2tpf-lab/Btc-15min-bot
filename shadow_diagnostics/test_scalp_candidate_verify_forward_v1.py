import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import scalp_candidate_verify_forward_v1 as cv


class CandidateVerifyForwardV1Tests(unittest.TestCase):
    def op(self, paths):
        return {
            "contract": "C1",
            "candidate_id": "X1",
            "opportunity_index": 1,
            "side": "UP",
            "entry_ask": .50,
            "seconds_left": 600.0,
            "plus5": 1,
            "plus10": 1,
            "plus20": 0,
            "peak_gain": .12,
            "adverse_gain": -.01,
            "protected_exit_gain": .04,
            "_candidate": {"timestamp_utc": "2026-09-16T12:00:00Z"},
            "_paths": paths,
        }

    def test_delayed_policy_cannot_inherit_pre_entry_peak(self):
        # Before 10s the old candidate had a huge executable gain.  At/after
        # the delayed entry, however, the new ASK is 60c and later BIDs never
        # get 10c above it.  The delayed policy must therefore be a +10 miss.
        paths = [
            {"elapsed_sec": 2, "current_ask": .50, "current_bid": .65},
            {"elapsed_sec": 10, "current_ask": .60, "current_bid": .59},
            {"elapsed_sec": 12, "current_ask": .61, "current_bid": .64},
            {"elapsed_sec": 20, "current_ask": .62, "current_bid": .66},
        ]
        r = cv.delayed_record(self.op(paths), 10.0)
        self.assertIsNotNone(r)
        self.assertEqual(r["entry_ask"], .60)
        self.assertEqual(r["plus10"], 0)
        self.assertAlmostEqual(r["peak_gain"], .06)
        self.assertAlmostEqual(r["entry_slippage_c_vs_candidate"], 10.0)
        self.assertEqual(r["actual_delay_sec"], 10.0)

    def test_protection_lifecycle_rebases_from_verified_entry(self):
        paths = [
            {"elapsed_sec": 1, "current_ask": .40, "current_bid": .70},  # pre-entry ignored
            {"elapsed_sec": 10, "current_ask": .40, "current_bid": .39},
            {"elapsed_sec": 12, "current_ask": .41, "current_bid": .46},  # +6c arms
            {"elapsed_sec": 14, "current_ask": .42, "current_bid": .42},  # +2c -> 4c giveback exit
        ]
        r = cv.delayed_record(self.op(paths), 10.0)
        self.assertIsNotNone(r)
        self.assertTrue(r["protected_exit_observed"])
        self.assertAlmostEqual(r["protected_exit_gain"], .02)
        self.assertAlmostEqual(r["gross_protected_gain_c"], 2.0)
        self.assertTrue(r["delayed_lifecycle_rebased"])
        self.assertIn("10", r["fee_scenarios"])

    def test_delayed_entry_requires_actual_then_current_ask(self):
        paths = [
            {"elapsed_sec": 5, "current_ask": .50, "current_bid": .50},
            {"elapsed_sec": 9, "current_ask": .51, "current_bid": .51},
            {"elapsed_sec": 12, "current_bid": .52},
        ]
        self.assertIsNone(cv.delayed_record(self.op(paths), 10.0))

    def test_future_universe_excludes_pre_cutoff(self):
        cutoff = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
        fake_full = {
            "OLD": {"first_seen": datetime(2026, 9, 16, 11, 59, tzinfo=timezone.utc)},
            "NEW": {"first_seen": datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)},
        }
        with patch.object(cv.adapter, "adapt_rows", return_value=[{"x": 1}]), \
             patch.object(cv.union, "full_contract_universe", return_value=fake_full):
            future, adapted = cv.future_universe([], cutoff)
        self.assertEqual(set(future), {"NEW"})
        self.assertEqual(adapted, [{"x": 1}])

    def test_policy_summary_retention_uses_immediate_denominator(self):
        rec = cv.immediate_record(self.op([]))
        out = cv.summarize_policy([rec], unavailable=2, immediate_signal_n=4,
                                  immediate_contract_n=2, future_contract_n=5)
        self.assertEqual(out["signal_retention_vs_immediate"], .25)
        self.assertEqual(out["contract_retention_vs_immediate"], .5)
        self.assertEqual(out["true_future_contract_coverage"], .2)
        self.assertEqual(out["unavailable_verified_entries"], 2)

    def test_analyze_is_comparison_only_and_starts_clean(self):
        with patch.object(cv, "future_universe", return_value=({}, [])), \
             patch.object(cv.q, "build_serial_opportunities", return_value=[]):
            out = cv.analyze_rows([], cutoff_text="2026-09-16T12:00:00Z")
        self.assertTrue(out["ok"])
        self.assertEqual(out["future_full_contracts"], 0)
        self.assertEqual(out["status"], "COLLECTING_FUTURE_CANDIDATE_VERIFY_V1")
        self.assertFalse(out["policy_selection"])
        self.assertFalse(out["same_sample_promotion"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])
        self.assertEqual(out["frozen_policies"]["delays_sec"], [0.0, 5.0, 10.0, 15.0, 30.0])

    def test_integrity_grid_and_lifecycle_frozen(self):
        self.assertEqual(cv.VERIFY_DELAYS_SEC, (0.0, 5.0, 10.0, 15.0, 30.0))
        cv.assert_integrity()


if __name__ == "__main__":
    unittest.main()
