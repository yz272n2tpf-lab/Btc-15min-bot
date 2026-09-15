#!/usr/bin/env python3
import unittest

import BTC15_SCALP_SERIAL_RUNTIME_PROJECTION_V1 as p


class SerialRuntimeProjectionTests(unittest.TestCase):
    CONTRACT = "KXBTC15M-26SEP150000-00"

    def candidate(self, ts, cid, ask="0.31", side="UP", left="600", btc30="20"):
        return {
            "record_type": "CANDIDATE", "timestamp_utc": ts,
            "candidate_id": cid, "contract": self.CONTRACT,
            "entry_ask": ask, "side": side, "seconds_left": left, "btc30": btc30,
        }

    def path(self, ts, cid, gain, elapsed):
        return {
            "record_type": "PATH", "timestamp_utc": ts,
            "candidate_id": cid, "contract": self.CONTRACT,
            "exec_gain": str(gain), "elapsed_sec": str(elapsed),
        }

    def result(self, ts, cid):
        return {
            "record_type": "RESULT", "timestamp_utc": ts,
            "candidate_id": cid, "contract": self.CONTRACT,
        }

    def test_completed_unarmed_hands_off_to_next_live_candidate(self):
        rows = [
            self.candidate("2026-09-15T00:00:00Z", "a"),
            self.path("2026-09-15T00:00:20Z", "a", 0.02, 20),
            self.result("2026-09-15T00:01:00Z", "a"),
            self.candidate("2026-09-15T00:01:10Z", "b", ask="0.44", side="DOWN"),
            self.path("2026-09-15T00:01:20Z", "b", 0.01, 10),
        ]
        out = p.build_state(rows, contract=self.CONTRACT)
        self.assertEqual(out["state"], "ACTIVE")
        self.assertEqual(out["candidate_id"], "b")
        self.assertEqual(out["opportunity_index"], 2)
        self.assertEqual(out["previous_terminal"]["state"], "ENDED_UNARMED")
        self.assertFalse(out["previous_terminal"]["actionable_exit"])
        self.assertTrue(out["actionable"])
        self.assertFalse(out["orders"])

    def test_completed_unarmed_without_next_candidate_is_informational_terminal(self):
        rows = [
            self.candidate("2026-09-15T00:00:00Z", "a"),
            self.path("2026-09-15T00:00:20Z", "a", -0.08, 20),
            self.result("2026-09-15T00:01:00Z", "a"),
        ]
        out = p.build_state(rows, contract=self.CONTRACT)
        self.assertEqual(out["state"], "ENDED_UNARMED")
        self.assertFalse(out["actionable"])
        self.assertTrue(out["reset_ready"])
        self.assertFalse(out["ended_unarmed_is_actionable_exit"])
        self.assertFalse(out["stop_loss_rule_selected"])

    def test_armed_completed_without_giveback_does_not_invent_exit_or_handoff(self):
        rows = [
            self.candidate("2026-09-15T00:00:00Z", "a"),
            self.path("2026-09-15T00:00:10Z", "a", 0.06, 10),
            self.path("2026-09-15T00:00:20Z", "a", 0.05, 20),
            self.result("2026-09-15T00:01:00Z", "a"),
            self.candidate("2026-09-15T00:01:10Z", "b"),
            self.path("2026-09-15T00:01:20Z", "b", 0.20, 10),
        ]
        out = p.build_state(rows, contract=self.CONTRACT)
        self.assertEqual(out["state"], "ARMED_NO_VALIDATED_EXIT")
        self.assertEqual(out["candidate_id"], "a")
        self.assertFalse(out["reset_ready"])
        self.assertFalse(out["actionable"])
        self.assertTrue(out["requires_rule_review"])

    def test_protected_exit_hands_off_to_high_price_candidate_without_filter(self):
        rows = [
            self.candidate("2026-09-15T00:00:00Z", "a", ask="0.22"),
            self.path("2026-09-15T00:00:10Z", "a", 0.07, 10),
            self.path("2026-09-15T00:00:20Z", "a", 0.02, 20),
            self.candidate("2026-09-15T00:00:30Z", "b", ask="0.88", side="DOWN"),
            self.path("2026-09-15T00:00:40Z", "b", 0.01, 10),
        ]
        out = p.build_state(rows, contract=self.CONTRACT)
        self.assertEqual(out["state"], "ACTIVE")
        self.assertEqual(out["candidate_id"], "b")
        self.assertAlmostEqual(out["entry_price"], 0.88)
        self.assertFalse(out["entry_price_filter_applied"])
        self.assertTrue(out["price_is_telemetry_only"])
        self.assertEqual(out["previous_terminal"]["state"], "PROTECTED_EXIT")

    def test_incomplete_first_candidate_cannot_be_skipped(self):
        rows = [
            self.candidate("2026-09-15T00:00:00Z", "a"),
            self.path("2026-09-15T00:00:10Z", "a", -0.10, 10),
            self.candidate("2026-09-15T00:00:20Z", "b"),
            self.path("2026-09-15T00:00:30Z", "b", 0.30, 10),
        ]
        out = p.build_state(rows, contract=self.CONTRACT)
        self.assertEqual(out["candidate_id"], "a")
        self.assertEqual(out["opportunity_index"], 1)
        self.assertEqual(out["state"], "ACTIVE")

    def test_unqualified_candidate_does_not_enter_ladder(self):
        rows = [
            self.candidate("2026-09-15T00:00:00Z", "bad", left="100"),
            self.candidate("2026-09-15T00:00:10Z", "good"),
        ]
        out = p.build_state(rows, contract=self.CONTRACT)
        self.assertEqual(out["candidate_id"], "good")
        self.assertEqual(out["opportunity_index"], 1)


if __name__ == "__main__":
    unittest.main()
