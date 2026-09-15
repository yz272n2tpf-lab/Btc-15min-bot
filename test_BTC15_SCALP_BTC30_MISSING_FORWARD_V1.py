#!/usr/bin/env python3
import unittest

import BTC15_SCALP_BTC30_MISSING_FORWARD_V1 as m


class BTC30MissingForwardTests(unittest.TestCase):
    def cand(self, cid, ts="2026-09-15T14:17:00Z", btc30="", ask="0.45", side="DOWN", left="850"):
        return {
            "record_type": "CANDIDATE",
            "contract": "KXBTC15M-X",
            "candidate_id": cid,
            "timestamp_utc": ts,
            "side": side,
            "entry_ask": ask,
            "seconds_left": left,
            "btc30": btc30,
        }

    def path(self, cid, ts, gain):
        return {
            "record_type": "PATH",
            "contract": "KXBTC15M-X",
            "candidate_id": cid,
            "timestamp_utc": ts,
            "exec_gain": str(gain),
        }

    def result(self, cid, ts="2026-09-15T14:18:00Z"):
        return {
            "record_type": "RESULT",
            "contract": "KXBTC15M-X",
            "candidate_id": cid,
            "timestamp_utc": ts,
        }

    def completed(self, c, peak=0.12):
        cid = c["candidate_id"]
        return [c, self.path(cid, "2026-09-15T14:17:10Z", peak), self.result(cid)]

    def test_cutoff_excludes_old_candidate(self):
        old = self.cand("old", ts="2026-09-15T14:15:59Z", btc30="20")
        self.assertEqual(m.fresh_raw_candidates([old]), [])

    def test_missing_btc30_is_hypothesis_only_not_baseline(self):
        c = self.cand("m1", btc30="")
        self.assertFalse(m.baseline_eligible(c))
        self.assertTrue(m.hypothesis_eligible(c))
        self.assertTrue(m.missing_btc30(c))

    def test_present_btc30_still_requires_15(self):
        low = self.cand("l", btc30="14.99")
        good = self.cand("g", btc30="15")
        self.assertFalse(m.hypothesis_eligible(low))
        self.assertTrue(m.hypothesis_eligible(good))

    def test_price_never_changes_eligibility(self):
        cheap = self.cand("a", btc30="", ask="0.25")
        expensive = self.cand("b", btc30="", ask="0.85")
        self.assertTrue(m.hypothesis_eligible(cheap))
        self.assertTrue(m.hypothesis_eligible(expensive))

    def test_missing_candidate_can_block_later_baseline_until_terminal(self):
        missing = self.cand("m1", btc30="", ask="0.45")
        base = self.cand("b1", ts="2026-09-15T14:17:20Z", btc30="20", ask="0.40")
        rows = [
            missing,
            self.path("m1", "2026-09-15T14:17:10Z", 0.12),
            self.result("m1", "2026-09-15T14:18:00Z"),
            base,
            self.path("b1", "2026-09-15T14:17:30Z", 0.20),
            self.result("b1", "2026-09-15T14:18:30Z"),
        ]
        baseline = m.build_serial(rows, m.baseline_eligible)
        hyp = m.build_serial(rows, m.hypothesis_eligible)
        self.assertEqual([r["candidate_id"] for r in baseline], ["b1"])
        self.assertEqual([r["candidate_id"] for r in hyp], ["m1"])
        self.assertFalse(hyp[0]["entry_price_is_telemetry_only"] is False)
        self.assertFalse(hyp[0]["orders"])

    def test_summary_remains_research_only_without_minimum_sample(self):
        c = self.cand("m1", btc30="", ask="0.45")
        rows = self.completed(c)
        s = m.summarize(rows)
        self.assertEqual(s["status"], "COLLECTING_FRESH_FORWARD")
        self.assertFalse(s["sample_ready"])
        self.assertFalse(s["acceptance_pass"])
        self.assertFalse(s["orders"])
        self.assertFalse(s["entry_price_filter_applied"])
        self.assertFalse(s["auto_promote_allowed"])
        self.assertFalse(s["production_behavior_changed"])

    def test_under_120_seconds_rejected_for_both(self):
        c = self.cand("x", btc30="", left="119")
        self.assertFalse(m.baseline_eligible(c))
        self.assertFalse(m.hypothesis_eligible(c))


if __name__ == "__main__":
    unittest.main()
