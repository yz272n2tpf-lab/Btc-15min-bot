#!/usr/bin/env python3
import unittest

import BTC15_SCALP_15S_PARITY_DIAGNOSTICS_V1 as m


class ParityDiagnosticsTests(unittest.TestCase):
    def rec(self, cid, *, ratio=1.0, plus10=False, plus20=False, ts="2026-09-15T04:52:00Z"):
        b15 = 20.0
        return {
            "candidate_id": cid,
            "contract": "KXBTC15M-TEST",
            "opportunity_index": 1,
            "timestamp_utc": ts,
            "side": "UP",
            "btc15": b15,
            "brti15": b15 * ratio,
            "parity_ratio": ratio,
            "plus10": plus10,
            "plus20": plus20,
            "terminal_kind": "ENDED_UNARMED",
        }

    def test_lost_winner_is_explicitly_exposed(self):
        summary = {
            "cutoff_utc": "2026-09-15T04:51:00Z",
            "hypothesis": "brti15/btc15 >= 1.00",
            "baseline_records": [
                self.rec("lost", ratio=.80, plus10=True),
                self.rec("kept", ratio=1.10, plus10=True, ts="2026-09-15T04:53:00Z"),
            ],
            "hypothesis_records": [self.rec("kept", ratio=1.10, plus10=True, ts="2026-09-15T04:53:00Z")],
        }
        d = m.diagnostics(summary)
        self.assertEqual(d["baseline_n"], 2)
        self.assertEqual(d["hypothesis_n"], 1)
        self.assertEqual(d["direct_rejected_n"], 1)
        self.assertEqual(d["lost_plus10_winners_n"], 1)
        self.assertEqual(d["retained_plus10_winners_n"], 1)
        self.assertEqual(d["lost_plus10_winners"][0]["candidate_id"], "lost")
        self.assertFalse(d["lost_plus10_winners"][0]["direct_parity_pass"])

    def test_diagnostics_remain_non_actionable(self):
        d = m.diagnostics({"baseline_records": [], "hypothesis_records": []})
        self.assertTrue(d["research_only"])
        self.assertTrue(d["manual_execution_only"])
        self.assertFalse(d["orders"])
        self.assertFalse(d["actionable_now"])
        self.assertFalse(d["production_behavior_changed"])


if __name__ == "__main__":
    unittest.main()
