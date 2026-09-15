import unittest

import BTC15_SCALP_SERIAL_STATE_BRIDGE_SHADOW_V1 as bridge


class SerialStateBridgeTests(unittest.TestCase):
    CONTRACT = "KXBTC15M-26SEP150000-00"

    def c(self, ts, cid, ask="0.31", side="UP", left="600", btc30="20"):
        return {"record_type":"CANDIDATE","timestamp_utc":ts,"candidate_id":cid,"contract":self.CONTRACT,"entry_ask":ask,"side":side,"seconds_left":left,"btc30":btc30}

    def p(self, ts, cid, gain, elapsed):
        return {"record_type":"PATH","timestamp_utc":ts,"candidate_id":cid,"contract":self.CONTRACT,"exec_gain":str(gain),"elapsed_sec":str(elapsed)}

    def r(self, ts, cid):
        return {"record_type":"RESULT","timestamp_utc":ts,"candidate_id":cid,"contract":self.CONTRACT}

    def s(self, ts, left="300"):
        return {"record_type":"SNAPSHOT","timestamp_utc":ts,"contract":self.CONTRACT,"seconds_left":left}

    def test_unarmed_result_resets_to_second_scalp(self):
        rows = [
            self.s("2026-09-15T00:02:00Z"),
            self.c("2026-09-15T00:00:00Z","a"),
            self.p("2026-09-15T00:00:20Z","a",0.02,20),
            self.r("2026-09-15T00:01:00Z","a"),
            self.c("2026-09-15T00:01:10Z","b",ask="0.42",side="DOWN"),
            self.p("2026-09-15T00:01:20Z","b",0.03,10),
        ]
        out = bridge.build_state(rows)
        self.assertEqual(out["terminal_history"][0]["terminal_state"], "ENDED_UNARMED")
        self.assertFalse(out["terminal_history"][0]["actionable_exit"])
        self.assertEqual(out["current"]["candidate_id"], "b")
        self.assertEqual(out["current"]["opportunity_index"], 2)
        self.assertEqual(out["current"]["state"], "ACTIVE")

    def test_protected_exit_resets_to_next_scalp(self):
        rows = [
            self.s("2026-09-15T00:02:00Z"),
            self.c("2026-09-15T00:00:00Z","a"),
            self.p("2026-09-15T00:00:10Z","a",0.06,10),
            self.p("2026-09-15T00:00:20Z","a",0.01,20),
            self.r("2026-09-15T00:00:40Z","a"),
            self.c("2026-09-15T00:00:30Z","b",ask="0.35"),
            self.p("2026-09-15T00:00:40Z","b",0.02,10),
        ]
        out = bridge.build_state(rows)
        self.assertEqual(out["terminal_history"][0]["terminal_state"], "EXIT")
        self.assertTrue(out["terminal_history"][0]["actionable_exit"])
        self.assertEqual(out["current"]["candidate_id"], "b")
        self.assertEqual(out["current"]["opportunity_index"], 2)

    def test_incomplete_first_scalp_stays_current_and_blocks_overlap(self):
        rows = [
            self.s("2026-09-15T00:02:00Z"),
            self.c("2026-09-15T00:00:00Z","a"),
            self.p("2026-09-15T00:00:20Z","a",-0.12,20),
            self.c("2026-09-15T00:00:30Z","b"),
            self.p("2026-09-15T00:00:40Z","b",0.20,10),
        ]
        out = bridge.build_state(rows)
        self.assertEqual(out["current"]["candidate_id"], "a")
        self.assertEqual(out["current"]["state"], "ACTIVE")
        self.assertEqual(out["serial_opportunities_completed"], 0)

    def test_high_price_second_scalp_is_not_filtered(self):
        rows = [
            self.s("2026-09-15T00:02:00Z"),
            self.c("2026-09-15T00:00:00Z","a"),
            self.p("2026-09-15T00:00:10Z","a",0.01,10),
            self.r("2026-09-15T00:00:40Z","a"),
            self.c("2026-09-15T00:00:50Z","b",ask="0.88",side="DOWN"),
            self.p("2026-09-15T00:01:00Z","b",0.02,10),
        ]
        out = bridge.build_state(rows)
        self.assertEqual(out["current"]["candidate_id"], "b")
        self.assertAlmostEqual(out["current"]["entry_price"], .88)
        self.assertIsNone(out["frozen_rule"]["entry_price_filter"])
        self.assertFalse(out["orders"])


if __name__ == "__main__":
    unittest.main()
