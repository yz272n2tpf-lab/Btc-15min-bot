#!/usr/bin/env python3
import unittest

import BTC15_ROLLOVER_DISCOVERY_GATE_V1 as g


def row(exact, broad, *, identity=True, clock=True):
    return {
        "exact_active_quoted": exact,
        "broad_active": broad,
        "identity_all": identity,
        "wrong_identity": not identity,
        "clock_all": clock,
        "wrong_clock": not clock,
    }


class RolloverGateTests(unittest.TestCase):
    def test_not_ready_before_four_rollovers(self):
        s = g.score([row(1, 20), row(2, 22), row(3, 25)])
        self.assertFalse(s["sample_ready"])
        self.assertFalse(s["pass"])
        self.assertEqual(s["status"], "COLLECTING_ROLLOVER_PROBE")

    def test_clean_four_rollover_sample_passes_to_shadow_only(self):
        s = g.score([row(1, 20), row(2, 22), row(3, 25), row(4, 28)])
        self.assertTrue(s["sample_ready"])
        self.assertTrue(s["pass"])
        self.assertEqual(s["status"], "READY_FOR_SHADOW_FALLBACK_TEST")
        self.assertEqual(s["exact_fast_rate"], 1.0)
        self.assertGreaterEqual(s["median_direct_lead_sec"], 10.0)
        self.assertFalse(s["auto_promote"])
        self.assertFalse(s["production_change_allowed"])
        self.assertFalse(s["orders"])

    def test_same_timing_rejects_fallback(self):
        s = g.score([row(1, 3), row(2, 4), row(3, 5), row(4, 6)])
        self.assertTrue(s["sample_ready"])
        self.assertFalse(s["pass"])
        self.assertEqual(s["status"], "REVIEW_SAMPLE_READY_REJECTED")
        self.assertFalse(s["criteria"]["median_direct_lead_ge_10s"])

    def test_wrong_clock_rejects_even_with_large_lead(self):
        s = g.score([row(1, 30), row(2, 30), row(3, 30), row(4, 30, clock=False)])
        self.assertTrue(s["sample_ready"])
        self.assertFalse(s["pass"])
        self.assertFalse(s["criteria"]["clock_correct_all"])

    def test_wrong_identity_rejects_even_with_large_lead(self):
        s = g.score([row(1, 30), row(2, 30), row(3, 30), row(4, 30, identity=False)])
        self.assertTrue(s["sample_ready"])
        self.assertFalse(s["pass"])
        self.assertFalse(s["criteria"]["identity_correct_all"])

    def test_only_three_of_four_need_be_fast(self):
        s = g.score([row(1, 30), row(2, 30), row(4, 30), row(7, 30)])
        self.assertEqual(s["exact_fast_rate"], 0.75)
        self.assertTrue(s["criteria"]["exact_active_quoted_by_5s_rate_ge_75pct"])


if __name__ == "__main__":
    unittest.main()
