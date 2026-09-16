#!/usr/bin/env python3
import unittest

import scalp_nextgen_shadow_v2 as v2


def op(strong=False, ask=.60, idx=2):
    cand = {"timestamp_utc":"2026-09-16T20:00:00+00:00", "confirm_count":2 if strong else 1,
            "structure_ok":strong, "brti_status":"PRIMARY_OK" if strong else "STALE",
            "btc_against_side":False, "brti_against_side":False, "dual_reversal_evidence":False}
    paths = [
        {"elapsed_sec":2,"exec_gain":0.0,"current_ask":ask,"current_bid":ask},
        {"elapsed_sec":4,"exec_gain":.01,"current_ask":ask+.01,"current_bid":ask+.01},
        {"elapsed_sec":8,"exec_gain":.06,"current_ask":ask+.07,"current_bid":ask+.06},
        {"elapsed_sec":10,"exec_gain":.055,"current_ask":ask+.06,"current_bid":ask+.055},
        {"elapsed_sec":12,"exec_gain":.01,"current_ask":ask+.02,"current_bid":ask+.01},
    ]
    return {"contract":"C","candidate_id":"X","opportunity_index":idx,"entry_ask":ask,
            "seconds_left":600,"btc_move5_norm":.8 if strong else .4,
            "btc_move15_norm":.7 if strong else .3,"_candidate":cand,"_paths":paths,
            "plus5":1,"plus10":0,"plus20":0,"protected_exit_gain":.01,
            "peak_gain":.06,"adverse_gain":0}


class TestNextgenV2(unittest.TestCase):
    def test_strong_can_confirm_immediately(self):
        r=v2.dynamic_verify_record(op(True)); self.assertEqual(r["verify_mode"],"IMMEDIATE_STRONG")
        self.assertEqual(r["actual_delay_sec"],0)
    def test_weak_requires_causal_events(self):
        r=v2.dynamic_verify_record(op(False)); self.assertEqual(r["verify_mode"],"EVENT_CONFIRMED")
        self.assertEqual(r["actual_delay_sec"],4)
    def test_dynamic_rejects_price_chase(self):
        x=op(False)
        for row in x["_paths"]:
            row["current_ask"]=x["entry_ask"]+.04
        self.assertIsNone(v2.dynamic_verify_record(x))
    def test_watch_exit_is_unchanged(self):
        r=v2.watch_measure(op(False),"V2_CONFIRMED_HALF_C")
        self.assertTrue(r["armed"]); self.assertTrue(r["exit"])
        lanes=v2.watch_lanes([op(False)])
        self.assertIn("avg_gross_protected_gain_c",lanes["V1_1C"])
        self.assertIn("one_lot_taker_taker_avg_net_c",lanes["V2_CONFIRMED_HALF_C"])
    def test_scalp2_only(self):
        lanes=v2.scalp2_lanes([op(False,idx=1),op(False,idx=2)],1)
        self.assertEqual(lanes["CONTROL_V1_SCALP2"]["signals"],1)
    def test_selective_immediate_when_affordable(self):
        r=v2.selective_pullback_record(op(False,ask=.49),"V2_BALANCED")
        self.assertEqual(r["entry_elapsed_sec"],0)
    def test_selective_pullback_can_pass(self):
        x=op(False,ask=.70)
        for row in x["_paths"]: row["current_ask"]=.65
        self.assertIsNone(v2.selective_pullback_record(x,"V2_PRICE_DISCIPLINED"))
    def test_invalid_cutoff_fails_closed(self):
        r=v2.analyze_rows([],cutoff_text="not-a-time")
        self.assertFalse(r["ok"]); self.assertEqual(r["status"],"FAIL_CLOSED_INVALID_CUTOFF")
        self.assertFalse(r["orders"])
    def test_watch_v2_never_changes_exit_count(self):
        lanes=v2.watch_lanes([op(False),op(False)])
        exits={x["frozen_exit_signals"] for x in lanes.values()}
        self.assertEqual(len(exits),1)
    def test_runtime_integrity_passes_only_complete_safe_state(self):
        state={"cutoff_utc":v2.DEFAULT_CUTOFF_UTC,"orders":False,"automatic_promotion":False,
               "same_sample_promotion":False,"production_logic_changed":False,
               "scalp2_economics_v2":{},"candidate_verify_v2":{},"selective_pullback_v2":{},
               "watch_exit_v2":{"A":{"frozen_exit_signals":3},"B":{"frozen_exit_signals":3}}}
        self.assertTrue(v2.integrity_report(state)["all_checks_pass"])
        state["watch_exit_v2"]["B"]["frozen_exit_signals"]=2
        self.assertFalse(v2.integrity_report(state)["all_checks_pass"])
    def test_no_orders_or_promotion(self):
        rules=v2.frozen_rules(); self.assertFalse(rules["orders"])
        self.assertFalse(rules["automatic_promotion"]); self.assertFalse(rules["same_sample_promotion"])
    def test_frozen_exit_constants(self):
        v2.assert_integrity()


if __name__ == "__main__": unittest.main()
