#!/usr/bin/env python3
import unittest

import BTC15_KALSHI_ROLLOVER_OPERATIONAL_GATE_V3 as g


def row(exact, broad, *, identity=True, clock=True):
    return {
        "exact_active_quoted": exact,
        "broad_active": broad,
        "identity_all": identity,
        "clock_all": clock,
    }


class OperationalGateV3Tests(unittest.TestCase):
    def test_collects_before_eight(self):
        s = g.score([row(10.0, 30.0)] * 7)
        self.assertEqual(s["status"], "COLLECTING_FRESH_OPERATIONAL_REPLICATION")
        self.assertFalse(s["sample_ready"])

    def test_passes_only_shadow_validation(self):
        rows = [row(10.0, 30.0)] * 7 + [row(16.0, 32.0)]
        s = g.score(rows)
        self.assertEqual(s["status"], "READY_FOR_EXACT_TICKER_SHADOW_VALIDATION")
        self.assertTrue(s["pass"])
        self.assertEqual(s["exact_active_quoted_by_15s_n"], 7)
        self.assertAlmostEqual(s["exact_active_quoted_by_15s_share"], 0.875)
        self.assertTrue(s["authorizes_shadow_validation_only"])
        self.assertFalse(s["authorizes_production_change"])
        self.assertFalse(s["orders"])

    def test_rejects_if_only_six_of_eight_by_15s(self):
        rows = [row(10.0, 30.0)] * 6 + [row(16.0, 35.0), row(17.0, 35.0)]
        s = g.score(rows)
        self.assertEqual(s["status"], "OPERATIONAL_REPLICATION_REJECTED")
        self.assertFalse(s["pass"])

    def test_rejects_identity_or_clock_failure(self):
        rows = [row(10.0, 30.0)] * 8
        rows[7]["identity_all"] = False
        self.assertFalse(g.score(rows)["pass"])
        rows[7]["identity_all"] = True
        rows[7]["clock_all"] = False
        self.assertFalse(g.score(rows)["pass"])

    def test_rejects_if_direct_does_not_precede_broad(self):
        rows = [row(10.0, 30.0)] * 7 + [row(10.0, 9.0)]
        s = g.score(rows)
        self.assertFalse(s["all_direct_before_broad"])
        self.assertFalse(s["pass"])

    def test_rejects_median_lead_under_15s(self):
        rows = [row(10.0, 22.0)] * 8
        s = g.score(rows)
        self.assertLess(s["median_lead_sec"], 15.0)
        self.assertFalse(s["pass"])

    def test_requires_six_comparisons(self):
        rows = [row(10.0, 30.0)] * 5 + [row(10.0, None)] * 3
        s = g.score(rows)
        self.assertFalse(s["sample_ready"])
        self.assertEqual(s["valid_comparisons"], 5)


if __name__ == "__main__":
    unittest.main()
