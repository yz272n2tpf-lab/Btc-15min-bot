#!/usr/bin/env python3
import unittest
from datetime import datetime, timezone

import BTC15_KALSHI_EXACT_ROLLOVER_FALLBACK_SHADOW_V1 as m

BOUNDARY = datetime(2026, 9, 15, 19, 45, tzinfo=timezone.utc)
NOW = datetime(2026, 9, 15, 19, 45, 4, tzinfo=timezone.utc)
EXPECTED = m.probe.ticker_for_boundary(BOUNDARY)


def exact(**overrides):
    d = {
        "exists": True,
        "returned_ticker": EXPECTED,
        "identity_match": True,
        "clock_match": True,
        "active": True,
        "yes_bid": 0.49,
        "yes_ask": 0.50,
        "no_bid": 0.50,
        "no_ask": 0.51,
    }
    d.update(overrides)
    return d


class ExactRolloverFallbackShadowTests(unittest.TestCase):
    def evaluate(self, production="OLD", **overrides):
        return m.evaluate_shadow(
            now=NOW,
            boundary=BOUNDARY,
            production_contract=production,
            exact=exact(**overrides),
        )

    def test_valid_exact_market_is_shadow_available_only_when_production_old(self):
        d = self.evaluate()
        self.assertTrue(d.shadow_fallback_available)
        self.assertEqual(d.reason, "SHADOW_FALLBACK_AVAILABLE")
        self.assertFalse(d.production_behavior_changed)
        self.assertFalse(d.orders)
        self.assertTrue(d.manual_execution_only)

    def test_production_already_caught_up_refuses_fallback(self):
        d = self.evaluate(production=EXPECTED)
        self.assertFalse(d.shadow_fallback_available)
        self.assertEqual(d.reason, "PRODUCTION_ALREADY_ON_EXPECTED_CONTRACT")

    def test_wrong_identity_refuses_fallback(self):
        d = self.evaluate(returned_ticker="WRONG", identity_match=False)
        self.assertFalse(d.shadow_fallback_available)
        self.assertEqual(d.reason, "WAIT_EXACT_IDENTITY")

    def test_wrong_clock_refuses_fallback(self):
        d = self.evaluate(clock_match=False)
        self.assertFalse(d.shadow_fallback_available)
        self.assertEqual(d.reason, "WAIT_EXACT_CLOCK")

    def test_inactive_market_refuses_fallback(self):
        d = self.evaluate(active=False)
        self.assertFalse(d.shadow_fallback_available)
        self.assertEqual(d.reason, "WAIT_EXACT_ACTIVE")

    def test_placeholder_book_refuses_fallback(self):
        d = self.evaluate(yes_bid=0.0, yes_ask=0.0, no_bid=1.0, no_ask=1.0)
        self.assertFalse(d.shadow_fallback_available)
        self.assertEqual(d.reason, "WAIT_USABLE_BOOK")

    def test_crossed_or_inverted_book_refuses_fallback(self):
        d = self.evaluate(yes_bid=0.55, yes_ask=0.54)
        self.assertFalse(d.shadow_fallback_available)
        self.assertEqual(d.reason, "WAIT_USABLE_BOOK")


if __name__ == "__main__":
    unittest.main()
