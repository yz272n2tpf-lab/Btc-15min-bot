#!/usr/bin/env python3
import unittest

from scalp_integration_state_bridge_v2 import build_state


def snap(contract="T", left=500, ts="2026-09-14T13:00:00Z"):
    return {"record_type":"SNAPSHOT","contract":contract,"seconds_left":left,"timestamp_utc":ts}


def cand(cid="C1", contract="T", left=480, btc30=20, side="UP", ask=.40, ts="2026-09-14T13:00:05Z"):
    return {
        "record_type":"CANDIDATE","candidate_id":cid,"contract":contract,
        "seconds_left":left,"btc30":btc30,"side":side,"entry_ask":ask,"timestamp_utc":ts,
    }


def path(gain, peak=None, elapsed=5, cid="C1", ts="2026-09-14T13:00:10Z"):
    return {
        "record_type":"PATH","candidate_id":cid,"elapsed_sec":elapsed,
        "exec_gain":gain,"peak_exec_gain":gain if peak is None else peak,
        "timestamp_utc":ts,
    }


class ScalpIntegrationStateBridgeTests(unittest.TestCase):
    def test_no_candidate_is_pass(self):
        x=build_state([snap()])
        self.assertEqual(x["state"],"PASS")
        self.assertFalse(x["armed"])
        self.assertIsNone(x["order_action"])

    def test_latest_snapshot_defines_current_contract(self):
        rows=[snap("OLD",left=10,ts="2026-09-14T12:59:59Z"),snap("NEW",left=800,ts="2026-09-14T13:00:00Z"),cand(contract="OLD")]
        x=build_state(rows)
        self.assertEqual(x["contract"],"NEW")
        self.assertEqual(x["state"],"PASS")

    def test_first_frozen_qualified_candidate_is_primary(self):
        rows=[snap(),cand(cid="BAD",left=119,ts="2026-09-14T13:00:01Z"),cand(cid="GOOD",left=470,btc30=25,side="DOWN",ask=.72,ts="2026-09-14T13:00:02Z")]
        x=build_state(rows)
        self.assertEqual(x["candidate_id"],"GOOD")
        self.assertEqual(x["state"],"ACTIVE")
        self.assertEqual(x["side"],"DOWN")
        self.assertAlmostEqual(x["entry_price"],.72)

    def test_price_never_filters_generalized_scalp(self):
        low=build_state([snap(),cand(ask=.05)])
        high=build_state([snap(),cand(ask=.95)])
        self.assertEqual(low["state"],"ACTIVE")
        self.assertEqual(high["state"],"ACTIVE")
        self.assertIsNone(low["frozen_rule"]["entry_price_filter"])

    def test_arm_surfaces_protect_immediately(self):
        x=build_state([snap(),cand(),path(.05)])
        self.assertEqual(x["state"],"PROTECT")
        self.assertEqual(x["management_message"],"PROTECT PROFITS")
        self.assertTrue(x["armed"])
        self.assertFalse(x["exit_triggered"])

    def test_big_winner_protects_before_exit(self):
        rows=[snap(),cand(),path(.05,elapsed=5,ts="2026-09-14T13:00:10Z"),path(.21,elapsed=10,ts="2026-09-14T13:00:15Z"),path(.19,peak=.21,elapsed=15,ts="2026-09-14T13:00:20Z")]
        x=build_state(rows)
        self.assertEqual(x["state"],"PROTECT")
        self.assertAlmostEqual(x["giveback_from_peak"],.02)

    def test_four_cent_giveback_is_exit(self):
        rows=[snap(),cand(),path(.05,elapsed=5,ts="2026-09-14T13:00:10Z"),path(.21,elapsed=10,ts="2026-09-14T13:00:15Z"),path(.17,peak=.21,elapsed=15,ts="2026-09-14T13:00:20Z")]
        x=build_state(rows)
        self.assertEqual(x["state"],"EXIT")
        self.assertEqual(x["management_message"],"EXIT / PROTECT PROFITS NOW")
        self.assertTrue(x["exit_triggered"])

    def test_manual_only_and_no_numeric_flip_risk(self):
        x=build_state([snap(),cand(),path(.08)])
        self.assertTrue(x["manual_execution_only"])
        self.assertIsNone(x["order_action"])
        self.assertFalse(x["numeric_flip_risk_validated"])
        self.assertFalse(x["owns_final_outcome"])
        self.assertFalse(x["owns_early_opportunity"])


if __name__ == "__main__":
    unittest.main()
