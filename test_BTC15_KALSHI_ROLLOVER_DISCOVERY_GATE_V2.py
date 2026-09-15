#!/usr/bin/env python3
import unittest

import BTC15_KALSHI_ROLLOVER_DISCOVERY_GATE_V2 as g


def row(exact, broad, *, identity=True, clock=True):
    return {
        "exact_active_quoted": exact,
        "broad_active": broad,
        "identity_all": identity,
        "clock_all": clock,
    }


class RolloverDiscoveryGateV2Tests(unittest.TestCase):
    def test_collecting_before_four_rollovers(self):
        s = g.score([row(4.0, 29.0), row(4.5, 30.0), row(5.0, 31.0)])
        self.assertEqual(s["status"], "COLLECTING")
        self.assertFalse(s["sample_ready"])
        self.assertFalse(s["pass"])

    def test_passes_only_shadow_fallback_gate(self):
        s = g.score([
            row(4.0, 29.0),
            row(4.5, 30.0),
            row(5.0, 31.0),
            row(4.8, 28.0),
        ])
        self.assertEqual(s["status"], "READY_FOR_SHADOW_FALLBACK_TEST")
        self.assertTrue(s["pass"])
        self.assertTrue(s["authorizes_shadow_fallback_test_only"])
        self.assertFalse(s["authorizes_production_change"])
        self.assertFalse(s["orders"])

    def test_rejects_if_fast_share_below_75_percent(self):
        s = g.score([
            row(4.0, 30.0),
            row(6.0, 30.0),
            row(7.0, 30.0),
            row(8.0, 30.0),
        ])
        self.assertEqual(s["status"], "REVIEW_SAMPLE_READY_REJECTED")
        self.assertFalse(s["pass"])

    def test_rejects_wrong_identity(self):
        s = g.score([
            row(4.0, 30.0),
            row(4.0, 30.0),
            row(4.0, 30.0),
            row(4.0, 30.0, identity=False),
        ])
        self.assertFalse(s["pass"])
        self.assertFalse(s["identity_all"])

    def test_rejects_wrong_clock(self):
        s = g.score([
            row(4.0, 30.0),
            row(4.0, 30.0),
            row(4.0, 30.0),
            row(4.0, 30.0, clock=False),
        ])
        self.assertFalse(s["pass"])
        self.assertFalse(s["clock_all"])

    def test_rejects_if_median_lead_under_ten_seconds(self):
        s = g.score([
            row(4.0, 12.0),
            row(4.0, 13.0),
            row(4.0, 13.5),
            row(4.0, 13.0),
        ])
        self.assertFalse(s["pass"])
        self.assertLess(s["median_lead_sec"], 10.0)


if __name__ == "__main__":
    unittest.main()
