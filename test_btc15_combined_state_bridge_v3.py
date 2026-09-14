#!/usr/bin/env python3
import unittest
from datetime import datetime, timezone

from btc15_combined_state_bridge_v3 import build_combined_state

NOW=datetime(2026,9,14,16,30,0,tzinfo=timezone.utc)

MAIN={
 "contract":"KXBTC15M-T",
 "timer":{"seconds_left":300.0,"minutes_left":5.0},
 "market":{"target":78000.0,"up_bid":.62,"up_ask":.63,"down_bid":.37,"down_ask":.38},
 "early":{"ready":True,"side":"UP","ask":.34,"fair":.79,"edge":.45},
 "final":{"ready":True,"side":"UP","confidence":.94,"recorded_final_call":False,
          "recorded_side":None,"recorded_confidence":None},
}

def iso(sec_ago):
    return datetime.fromtimestamp(NOW.timestamp()-sec_ago,tz=timezone.utc).isoformat().replace("+00:00","Z")

def rows(sec_ago=1):
    return [
      {"record_type":"SNAPSHOT","contract":"KXBTC15M-T","seconds_left":298.5,"timestamp_utc":iso(sec_ago)},
      {"record_type":"CANDIDATE","candidate_id":"C1","contract":"KXBTC15M-T","side":"DOWN",
       "seconds_left":420,"entry_ask":.40,"btc30":22.0,"timestamp_utc":iso(sec_ago)},
      {"record_type":"PATH","candidate_id":"C1","exec_gain":.06,"peak_exec_gain":.06,
       "elapsed_sec":5,"timestamp_utc":iso(sec_ago)},
    ]

class CombinedStateBridgeV3Tests(unittest.TestCase):
    def test_real_nested_schema_composes(self):
        x=build_combined_state(MAIN,rows(),now=NOW)
        self.assertEqual(x["version"],"BTC15_COMBINED_STATE_BRIDGE_V3")
        self.assertAlmostEqual(x["canonical_seconds_left"],300.0)
        self.assertAlmostEqual(x["scalp_timer_delta_sec"],1.5)
        self.assertEqual(x["early"]["state"],"QUALIFIED")
        self.assertEqual(x["final"]["state"],"LOCK")
        self.assertEqual(x["scalp"]["state"],"PROTECT")
        self.assertIn("COUNTERTREND_SCALP",x["context_labels"])

    def test_stale_scalp_fails_closed_only_scalp(self):
        x=build_combined_state(MAIN,rows(30),now=NOW)
        self.assertEqual(x["early"]["state"],"QUALIFIED")
        self.assertEqual(x["final"]["state"],"LOCK")
        self.assertEqual(x["scalp"]["state"],"PASS")
        self.assertFalse(x["scalp_source_fresh"])

    def test_signal_only(self):
        x=build_combined_state(MAIN,rows(),now=NOW)
        self.assertTrue(x["manual_execution_only"])
        self.assertIsNone(x["order_action"])
        self.assertFalse(x["numeric_flip_risk_validated"])
        self.assertFalse(x["orders"])

if __name__=="__main__":unittest.main()
