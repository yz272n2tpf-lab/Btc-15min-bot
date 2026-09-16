import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import scalp_regime_forward_observation_v1_1 as fwd


class RegimeForwardObservationV11Tests(unittest.TestCase):
    def test_parse_cutoff_is_utc_aware(self):
        x = fwd.parse_cutoff("2026-09-16T12:00:00Z")
        self.assertIsNotNone(x)
        self.assertEqual(x.tzinfo, timezone.utc)
        self.assertEqual(x.hour, 12)
        self.assertIsNone(fwd.parse_cutoff("not-a-time"))

    def test_future_universe_excludes_pre_cutoff_contract(self):
        cutoff = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
        fake_full = {
            "OLD": {"first_seen": datetime(2026, 9, 16, 11, 59, tzinfo=timezone.utc)},
            "NEW": {"first_seen": datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)},
        }
        with patch.object(fwd.adapter, "adapt_rows", return_value=[{"x": 1}]), \
             patch.object(fwd.union, "full_contract_universe", return_value=fake_full):
            future, adapted = fwd.future_universe([], cutoff)
        self.assertEqual(set(future), {"NEW"})
        self.assertEqual(adapted, [{"x": 1}])

    def test_tag_incidence_uses_true_future_contract_denominator(self):
        rows = [
            {"contract": "A", "tags": ["KALSHI_LAG", "TREND_ALIGNED"], "primary_regime": "KALSHI_LAG"},
            {"contract": "A", "tags": ["KALSHI_LAG"], "primary_regime": "KALSHI_LAG"},
            {"contract": "B", "tags": ["OTHER"], "primary_regime": "OTHER"},
        ]
        overlap = fwd.tag_incidence(rows, 4, primary=False)
        primary = fwd.tag_incidence(rows, 4, primary=True)
        self.assertEqual(overlap["KALSHI_LAG"]["contracts"], 1)
        self.assertEqual(overlap["KALSHI_LAG"]["true_future_contract_incidence"], .25)
        self.assertEqual(primary["OTHER"]["true_future_contract_incidence"], .25)

    def test_analyze_starts_clean_and_never_promotes(self):
        with patch.object(fwd, "future_universe", return_value=({}, [])), \
             patch.object(fwd, "build_future_records", return_value=[]):
            out = fwd.analyze_rows([], sha="abc", source_bytes=0,
                                   cutoff_text="2026-09-16T12:00:00Z")
        self.assertTrue(out["ok"])
        self.assertEqual(out["future_full_contracts"], 0)
        self.assertEqual(out["serial_covered_contracts"], 0)
        self.assertEqual(out["status"], "COLLECTING_FUTURE_REGIME_OBSERVATION_V1_1")
        self.assertFalse(out["evidence_readiness"]["sample_ready"])
        self.assertTrue(out["no_threshold_selection"])
        self.assertTrue(out["no_signal_suppression_or_rescue"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])

    def test_readiness_is_descriptive_not_pass_fail(self):
        records = []
        # econ compact metrics are patched so sample readiness can be tested
        # without synthesizing future price paths.
        fake_overall = {"protected_exit_signals": 50, "signals": 50}
        fake_future = {
            f"C{i}": {"first_seen": datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)}
            for i in range(100)
        }
        with patch.object(fwd, "future_universe", return_value=(fake_future, [])), \
             patch.object(fwd, "build_future_records", return_value=records), \
             patch.object(fwd, "compact_metrics", return_value=fake_overall):
            out = fwd.analyze_rows([], cutoff_text="2026-09-16T12:00:00Z")
        self.assertTrue(out["evidence_readiness"]["sample_ready"])
        self.assertEqual(out["status"], "READY_FOR_MANUAL_DESCRIPTIVE_REVIEW")
        self.assertTrue(out["evidence_readiness"]["readiness_is_not_a_pass_fail_or_promotion_gate"])
        self.assertFalse(out["automatic_promotion"])


if __name__ == "__main__":
    unittest.main()
