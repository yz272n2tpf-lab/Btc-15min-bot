#!/usr/bin/env python3
import unittest

from scalp_integration_state_bridge_v3 import build_state


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


class ScalpIntegrationStateBridgeV3Tests(unittest.TestCase):
    def test_state_payload_is_signal_only(self):
        x=build_state([snap(),cand()])
        self.assertEqual(x["version"],"GENERALIZED_SCALP_INTEGRATION_V3")
        self.assertTrue(x["manual_execution_only"])
        self.assertIsNone(x["order_action"])
        self.assertFalse(x["numeric_flip_risk_validated"])
        self.assertFalse(x["owns_final_outcome"])
        self.assertFalse(x["owns_early_opportunity"])

    def test_plus_five_at_peak_arms_protection_without_false_exit(self):
        x=build_state([snap(),cand(),path(.05)])
        self.assertEqual(x["state"],"PROTECT")
        self.assertEqual(x["management_message"],"PROTECTION ARMED · WINNER RUNNING")
        self.assertTrue(x["armed"])
        self.assertFalse(x["pullback_detected"])
        self.assertFalse(x["exit_triggered"])

    def test_twenty_one_cent_winner_at_peak_stays_running(self):
        rows=[snap(),cand(),path(.05,elapsed=5,ts="2026-09-14T13:00:10Z"),path(.21,elapsed=10,ts="2026-09-14T13:00:15Z")]
        x=build_state(rows)
        self.assertEqual(x["management_message"],"PROTECTION ARMED · WINNER RUNNING")
        self.assertAlmostEqual(x["peak_exec_gain"],.21)
        self.assertAlmostEqual(x["exec_gain"],.21)

    def test_first_one_cent_pullback_warns_before_exit(self):
        rows=[snap(),cand(),path(.05,elapsed=5,ts="2026-09-14T13:00:10Z"),path(.21,elapsed=10,ts="2026-09-14T13:00:15Z"),path(.20,peak=.21,elapsed=11,ts="2026-09-14T13:00:16Z")]
        x=build_state(rows)
        self.assertEqual(x["state"],"PROTECT")
        self.assertEqual(x["management_message"],"PROTECT PROFITS · PULLBACK DETECTED")
        self.assertTrue(x["pullback_detected"])
        self.assertFalse(x["exit_triggered"])
        self.assertAlmostEqual(x["giveback_from_peak"],.01)

    def test_four_cent_giveback_is_exit(self):
        rows=[snap(),cand(),path(.05,elapsed=5,ts="2026-09-14T13:00:10Z"),path(.21,elapsed=10,ts="2026-09-14T13:00:15Z"),path(.17,peak=.21,elapsed=11,ts="2026-09-14T13:00:16Z")]
        x=build_state(rows)
        self.assertEqual(x["state"],"EXIT")
        self.assertEqual(x["management_message"],"EXIT / PROTECT PROFITS NOW")
        self.assertTrue(x["pullback_detected"])
        self.assertTrue(x["exit_triggered"])

    def test_exit_remains_latched_after_later_recovery(self):
        rows=[
            snap(), cand(),
            path(.05,elapsed=5,ts="2026-09-14T13:00:10Z"),
            path(.11,elapsed=10,ts="2026-09-14T13:00:15Z"),
            path(.06,peak=.11,elapsed=15,ts="2026-09-14T13:00:20Z"),
            path(.15,peak=.15,elapsed=20,ts="2026-09-14T13:00:25Z"),
            path(.18,peak=.18,elapsed=25,ts="2026-09-14T13:00:30Z"),
        ]
        x=build_state(rows)
        self.assertEqual(x["state"],"EXIT")
        self.assertEqual(x["management_message"],"EXIT / PROTECT PROFITS NOW")
        self.assertAlmostEqual(x["peak_exec_gain"],.11)
        self.assertAlmostEqual(x["exec_gain"],.06)
        self.assertAlmostEqual(x["giveback_from_peak"],.05)

    def test_high_entry_price_remains_eligible(self):
        x=build_state([snap(),cand(ask=.95)])
        self.assertEqual(x["state"],"ACTIVE")
        self.assertIsNone(x["frozen_rule"]["entry_price_filter"])


if __name__ == "__main__":
    unittest.main()
