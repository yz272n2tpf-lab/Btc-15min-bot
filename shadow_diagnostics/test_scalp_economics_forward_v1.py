import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import scalp_economics_forward_v1 as fw

UTC = timezone.utc


class ScalpEconomicsForwardV1Tests(unittest.TestCase):
    def test_cutoff_required(self):
        out = fw.analyze_rows([], cutoff_text="")
        self.assertFalse(out["ok"])
        self.assertEqual(out["status"], "FAIL_CLOSED_MISSING_OR_INVALID_CUTOFF")
        self.assertFalse(out["orders"])

    def test_future_universe_excludes_contract_first_seen_before_cutoff(self):
        cutoff = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
        fake_adapted = [{"contract": "OLD"}, {"contract": "NEW"}]
        fake_full = {
            "OLD": {"first_seen": datetime(2026, 9, 16, 11, 59, tzinfo=UTC)},
            "NEW": {"first_seen": datetime(2026, 9, 16, 12, 1, tzinfo=UTC)},
        }
        with patch.object(fw.adapter, "adapt_rows", return_value=fake_adapted), \
             patch.object(fw.union, "full_contract_universe", return_value=fake_full):
            contracts, adapted = fw.future_universe([], cutoff)
        self.assertEqual(contracts, {"NEW"})
        self.assertEqual(adapted, fake_adapted)

    def test_future_records_only_keep_contracts_in_frozen_universe(self):
        fake = [
            {"contract": "A", "opportunity_index": 1},
            {"contract": "B", "opportunity_index": 2},
        ]
        with patch.object(fw.econ, "build_records", return_value=fake):
            out = fw.future_economics_records([], {"B"})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["contract"], "B")

    def test_lanes_are_independent(self):
        rows = [
            {"opportunity_index": 1}, {"opportunity_index": 2},
            {"opportunity_index": 3}, {"opportunity_index": 4},
        ]
        lanes = fw.lane_records(rows)
        self.assertEqual(len(lanes["SCALP_1"]), 1)
        self.assertEqual(len(lanes["SCALP_2"]), 1)
        self.assertEqual(len(lanes["SCALP_3_PLUS"]), 2)
        self.assertEqual(len(lanes["OVERALL"]), 4)

    def test_lane_cannot_pass_before_sample_ready(self):
        summary = {
            "protected_exit_signals": 19,
            "fee_adjusted_protected_exits": {
                "1": {"TAKER_TAKER": {"avg_net_gain_c_per_contract": 2.0,
                                          "median_net_gain_c_per_contract": 1.0,
                                          "positive_net_rate": .60}},
                "10": {"TAKER_TAKER": {"avg_net_gain_c_per_contract": 3.0,
                                           "median_net_gain_c_per_contract": 2.0,
                                           "positive_net_rate": .60}},
            },
        }
        g = fw.lane_gate("SCALP_2", summary, 100)
        self.assertFalse(g["sample_ready"])
        self.assertTrue(g["economic_conditions"]["break_even_evidence_pass"])
        self.assertFalse(g["manual_review_break_even_evidence_pass"])

    def test_break_even_gate_requires_both_1_and_10_lot(self):
        summary = {
            "protected_exit_signals": 50,
            "fee_adjusted_protected_exits": {
                "1": {"TAKER_TAKER": {"avg_net_gain_c_per_contract": 2.0,
                                          "median_net_gain_c_per_contract": 1.0,
                                          "positive_net_rate": .51}},
                "10": {"TAKER_TAKER": {"avg_net_gain_c_per_contract": -0.1,
                                           "median_net_gain_c_per_contract": 1.0,
                                           "positive_net_rate": .60}},
            },
        }
        flags = fw.economic_conditions(summary)
        self.assertTrue(flags["by_lot"]["1"]["break_even_evidence_pass"])
        self.assertFalse(flags["by_lot"]["10"]["break_even_evidence_pass"])
        self.assertFalse(flags["break_even_evidence_pass"])

    def test_ready_status_is_manual_review_not_auto_promotion(self):
        summaries = {
            "signals": 50,
            "protected_exit_signals": 50,
            "fee_adjusted_protected_exits": {
                "1": {"TAKER_TAKER": {"avg_net_gain_c_per_contract": 1.0,
                                          "median_net_gain_c_per_contract": 1.0,
                                          "positive_net_rate": .51}},
                "10": {"TAKER_TAKER": {"avg_net_gain_c_per_contract": 1.0,
                                           "median_net_gain_c_per_contract": 1.0,
                                           "positive_net_rate": .51}},
            },
        }
        with patch.object(fw, "future_universe", return_value=({f"C{i}" for i in range(100)}, [])), \
             patch.object(fw, "future_economics_records", return_value=[]), \
             patch.object(fw, "lane_records", return_value={"OVERALL": [], "SCALP_1": [], "SCALP_2": [], "SCALP_3_PLUS": []}), \
             patch.object(fw.econ, "summarize", return_value=summaries):
            out = fw.analyze_rows([], cutoff_text="2026-09-16T12:00:00Z")
        self.assertEqual(out["status"], "READY_FOR_MANUAL_ECONOMICS_REVIEW")
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])


if __name__ == "__main__":
    unittest.main()
