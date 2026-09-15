#!/usr/bin/env python3
import unittest

import BTC15_SCALP_BTC30_MISSING_COVERAGE_AUDIT_V1 as m


class BTC30MissingCoverageAuditTests(unittest.TestCase):
    def base(self, cid="x1", ask="0.45", btc30=""):
        return {
            "record_type": "CANDIDATE",
            "contract": "KXBTC15M-X",
            "candidate_id": cid,
            "timestamp_utc": "2026-09-15T12:00:00Z",
            "side": "DOWN",
            "entry_ask": ask,
            "seconds_left": "855",
            "btc30": btc30,
            "btc15": "50",
            "btc5": "30",
        }

    def result(self, cid="x1"):
        return {
            "record_type": "RESULT",
            "contract": "KXBTC15M-X",
            "candidate_id": cid,
            "timestamp_utc": "2026-09-15T12:02:00Z",
        }

    def path(self, cid="x1", gain="0.12", elapsed="10"):
        return {
            "record_type": "PATH",
            "contract": "KXBTC15M-X",
            "candidate_id": cid,
            "timestamp_utc": "2026-09-15T12:00:10Z",
            "elapsed_sec": elapsed,
            "exec_gain": gain,
        }

    def test_missing_btc30_completed_candidate_is_counted(self):
        out = m.audit([self.base(), self.path(), self.result()])
        self.assertEqual(out["completed_missing_btc30_rejects"], 1)
        self.assertEqual(out["plus10_n"], 1)
        self.assertEqual(out["entry_at_or_below_50c_n"], 1)
        self.assertTrue(out["hypothesis_generation_only"])
        self.assertFalse(out["frozen_v5_rule_changed"])
        self.assertFalse(out["rule_selected"])
        self.assertFalse(out["orders"])

    def test_present_btc30_is_not_part_of_missing_group(self):
        out = m.audit([self.base(btc30="20"), self.path(), self.result()])
        self.assertEqual(out["completed_missing_btc30_rejects"], 0)

    def test_incomplete_candidate_is_not_scored(self):
        out = m.audit([self.base(), self.path()])
        self.assertEqual(out["completed_missing_btc30_rejects"], 0)

    def test_under_120_seconds_is_not_recovery_group(self):
        c = self.base()
        c["seconds_left"] = "119"
        out = m.audit([c, self.path(), self.result()])
        self.assertEqual(out["completed_missing_btc30_rejects"], 0)

    def test_price_is_telemetry_only(self):
        out = m.audit([self.base(ask="0.80"), self.path(), self.result()])
        self.assertEqual(out["completed_missing_btc30_rejects"], 1)
        self.assertEqual(out["entry_at_or_below_50c_n"], 0)
        self.assertFalse(out["price_filter_applied"])


if __name__ == "__main__":
    unittest.main()
