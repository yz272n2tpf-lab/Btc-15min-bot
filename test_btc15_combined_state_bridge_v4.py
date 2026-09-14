#!/usr/bin/env python3
from __future__ import annotations

import inspect
import unittest

import btc15_combined_state_bridge_v4 as bridge


class FakeCache:
    def __init__(self, rows): self.rows=list(rows)
    def state_rows(self): return [dict(r) for r in self.rows]
    def diagnostics(self): return {"state_rows":len(self.rows),"orders":False}


def main_state(contract="KXBTC15M-X"):
    return {
        "contract":contract,
        "timer":{"seconds_left":300.0},
        "market":{"target":78000.0,"up_bid":.39,"up_ask":.41,"down_bid":.59,"down_ask":.61},
        "early":{"ready":True,"side":"UP","ask":.41,"fair":.80,"edge":.12},
        "final":{"ready":False,"recorded_final_call":False,"side":"UP","confidence":.88},
    }


def scalp_rows(contract="KXBTC15M-X"):
    return [
        {"record_type":"SNAPSHOT","timestamp_utc":"2026-09-14T17:00:00Z","contract":contract,"seconds_left":"300"},
        {"record_type":"CANDIDATE","timestamp_utc":"2026-09-14T17:00:01Z","contract":contract,"candidate_id":"c1","side":"UP","seconds_left":"300","entry_ask":"0.30","btc30":"20"},
        {"record_type":"PATH","timestamp_utc":"2026-09-14T17:00:02Z","contract":contract,"candidate_id":"c1","elapsed_sec":"1","exec_gain":"0.03"},
    ]


class CombinedStateBridgeV4Tests(unittest.TestCase):
    def setUp(self):
        self.old=bridge.CACHE
        bridge.CACHE=FakeCache(scalp_rows())
    def tearDown(self):
        bridge.CACHE=self.old

    def test_build_preserves_protected_main_and_generalized_scalp(self):
        d=bridge.build_combined_state(main_state())
        self.assertEqual(d["version"],"BTC15_COMBINED_STATE_BRIDGE_V4")
        self.assertEqual(d["contract"],"KXBTC15M-X")
        self.assertEqual(d["early"]["state"],"QUALIFIED")
        self.assertEqual(d["early"]["ask"],.41)
        self.assertEqual(d["early"]["fair"],.80)
        self.assertEqual(d["final"]["state"],"WATCH")
        self.assertEqual(d["scalp"]["state"],"ACTIVE")
        self.assertEqual(d["scalp_cache_mode"],"INCREMENTAL_APPEND_ONLY_V1")
        self.assertTrue(d["manual_execution_only"])
        self.assertFalse(d["orders"])
        self.assertIsNone(d["order_action"])
        self.assertFalse(d["numeric_flip_risk_validated"])

    def test_contract_mismatch_fails_scalp_closed(self):
        bridge.CACHE=FakeCache(scalp_rows("OTHER"))
        d=bridge.build_combined_state(main_state("MAIN"))
        self.assertEqual(d["scalp"]["state"],"PASS")
        self.assertFalse(d["scalp_contract_aligned"])
        self.assertEqual(d["scalp_management_message"],"SCALP WAIT · CONTRACT SYNC")
        self.assertNotIn("SCALP",d["actionable_paths"])

    def test_bridge_never_calls_full_tape_reader_per_request(self):
        src=inspect.getsource(bridge)
        self.assertNotIn("base.read_rows(",src)
        self.assertIn("CACHE.state_rows()",src)
        self.assertIn("INCREMENTAL CACHE",src)

    def test_no_order_methods_or_actions(self):
        src=inspect.getsource(bridge)
        self.assertNotIn("place_order",src)
        self.assertNotIn("create_order",src)
        self.assertNotIn("cancel_order",src)
        d=bridge.build_combined_state(main_state())
        self.assertFalse(d["orders"])
        self.assertIsNone(d["order_action"])


if __name__=="__main__":unittest.main()
