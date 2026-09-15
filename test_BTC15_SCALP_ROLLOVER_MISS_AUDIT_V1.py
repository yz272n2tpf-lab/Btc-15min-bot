#!/usr/bin/env python3
import unittest

import BTC15_SCALP_ROLLOVER_MISS_AUDIT_V1 as m


class RolloverMissAuditTests(unittest.TestCase):
    def cand(self, btc30="20", ask="0.45"):
        return {
            "record_type": "CANDIDATE",
            "contract": "KXBTC15M-26SEP151000-00",
            "candidate_id": "x1",
            "timestamp_utc": "2026-09-15T13:45:44.935Z",
            "side": "DOWN",
            "entry_ask": ask,
            "seconds_left": "855",
            "btc30": btc30,
            "btc15": "79.48",
            "btc5": "49.28",
        }

    def test_qualified_candidate_is_flagged_for_sync_review(self):
        out = m.diagnose([self.cand()])
        self.assertEqual(out["conclusion"], "V5_QUALIFIED_CANDIDATE_REQUIRES_SYNC_HANDOFF_REVIEW")
        self.assertTrue(out["target"]["v5_adapter_qualified"])
        self.assertEqual(out["target"]["adapter_initial_state"], "ACTIVE")
        self.assertFalse(out["orders"])
        self.assertFalse(out["strategy_change_selected"])
        self.assertFalse(out["price_filter_applied"])

    def test_btc30_below_floor_is_correctly_rejected(self):
        out = m.diagnose([self.cand(btc30="14.99")])
        self.assertEqual(out["conclusion"], "CORRECTLY_REJECTED_BY_FROZEN_V5_ADAPTER")
        self.assertFalse(out["target"]["v5_adapter_qualified"])
        self.assertEqual(out["target"]["adapter_initial_state"], "PASS")

    def test_under_120_seconds_is_rejected(self):
        c = self.cand()
        c["seconds_left"] = "119"
        out = m.diagnose([c])
        self.assertFalse(out["target"]["v5_adapter_qualified"])

    def test_wrong_entry_does_not_match_target(self):
        out = m.diagnose([self.cand(ask="0.80")])
        self.assertEqual(out["conclusion"], "TARGET_NOT_FOUND")
        self.assertIsNone(out["target"])

    def test_wrong_contract_does_not_match_target(self):
        c = self.cand()
        c["contract"] = "OTHER"
        out = m.diagnose([c])
        self.assertEqual(out["conclusion"], "TARGET_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
