#!/usr/bin/env python3
import unittest
from datetime import datetime, timezone, timedelta

import scalp_entry_profit_ladder_v1 as m

BASE = datetime(2026, 9, 16, 6, 0, tzinfo=timezone.utc)


def iso(sec):
    return (BASE + timedelta(seconds=sec)).isoformat()


def cand(cid="c1", contract="KXBTC-1", sec=0, ask=.70, left=780, btc30=25):
    return {"record_type":"CANDIDATE","candidate_id":cid,"contract":contract,"side":"UP",
            "timestamp_utc":iso(sec),"entry_ask":ask,"seconds_left":left,"btc30":btc30}


def path(cid="c1", sec=0, ask=.70, bid=.69):
    return {"record_type":"PATH","candidate_id":cid,"timestamp_utc":iso(sec),
            "elapsed_sec":sec if cid == "c1" else None,"current_ask":ask,"current_bid":bid}


def result(cid="c1"):
    return {"record_type":"RESULT","candidate_id":cid}


class EntryProfitLadderTests(unittest.TestCase):
    def test_affordable_wait_uses_actual_later_ask(self):
        c = cand(ask=.70)
        ps = [
            {"record_type":"PATH","candidate_id":"c1","timestamp_utc":iso(10),"elapsed_sec":10,"current_ask":.60,"current_bid":.59},
            {"record_type":"PATH","candidate_id":"c1","timestamp_utc":iso(20),"elapsed_sec":20,"current_ask":.48,"current_bid":.47},
            {"record_type":"PATH","candidate_id":"c1","timestamp_utc":iso(30),"elapsed_sec":30,"current_ask":.61,"current_bid":.60},
        ]
        e = m.choose_entry(c, ps, m.ENTRY_POLICIES["AFFORDABLE_30"])
        self.assertIsNotNone(e)
        self.assertAlmostEqual(e["entry_ask"], .48)
        self.assertEqual(e["entry_elapsed_sec"], 20)
        x = m.simulate_exit(c, ps, e, m.EXIT_POLICIES["LEGACY_5_4"])
        self.assertTrue(x["hit10"])  # .60 bid - .48 actual delayed ask

    def test_ideal_band_is_real_entry_not_original_price(self):
        c = cand(ask=.55)
        ps = [
            {"record_type":"PATH","candidate_id":"c1","timestamp_utc":iso(20),"elapsed_sec":20,"current_ask":.40,"current_bid":.39},
            {"record_type":"PATH","candidate_id":"c1","timestamp_utc":iso(40),"elapsed_sec":40,"current_ask":.31,"current_bid":.30},
        ]
        e = m.choose_entry(c, ps, m.ENTRY_POLICIES["IDEAL_25_35_60"])
        self.assertAlmostEqual(e["entry_ask"], .31)
        self.assertTrue(e["ideal_25_35"])

    def test_tighter_profit_trail_protects_earlier(self):
        c = cand(ask=.40)
        ps = [
            {"record_type":"PATH","candidate_id":"c1","timestamp_utc":iso(5),"elapsed_sec":5,"current_ask":.46,"current_bid":.45},
            {"record_type":"PATH","candidate_id":"c1","timestamp_utc":iso(10),"elapsed_sec":10,"current_ask":.49,"current_bid":.48},
            {"record_type":"PATH","candidate_id":"c1","timestamp_utc":iso(15),"elapsed_sec":15,"current_ask":.46,"current_bid":.45},
            {"record_type":"PATH","candidate_id":"c1","timestamp_utc":iso(20),"elapsed_sec":20,"current_ask":.44,"current_bid":.43},
        ]
        e = m.choose_entry(c, ps, m.ENTRY_POLICIES["IMMEDIATE"])
        tight = m.simulate_exit(c, ps, e, m.EXIT_POLICIES["PROTECT_5_3"])
        legacy = m.simulate_exit(c, ps, e, m.EXIT_POLICIES["LEGACY_5_4"])
        self.assertTrue(tight["protected_exit"])
        self.assertTrue(legacy["protected_exit"])
        self.assertEqual(tight["exit_elapsed_sec"], 15)
        self.assertEqual(legacy["exit_elapsed_sec"], 20)
        self.assertGreater(tight["protected_exit_gain"], legacy["protected_exit_gain"])

    def test_serial_reentry_requires_real_protected_exit(self):
        c1 = cand("c1", sec=0, ask=.40)
        c2 = cand("c2", sec=100, ask=.40)
        rows = [c1, c2, result("c1"), result("c2")]
        for cid, base in (("c1", 0), ("c2", 100)):
            rows += [
                {"record_type":"PATH","candidate_id":cid,"timestamp_utc":iso(base+5),"elapsed_sec":5,"current_ask":.46,"current_bid":.45},
                {"record_type":"PATH","candidate_id":cid,"timestamp_utc":iso(base+10),"elapsed_sec":10,"current_ask":.49,"current_bid":.48},
                {"record_type":"PATH","candidate_id":cid,"timestamp_utc":iso(base+20),"elapsed_sec":20,"current_ask":.44,"current_bid":.43},
            ]
        legacy = m.simulate_ladder(rows, m.ENTRY_POLICIES["IMMEDIATE"], m.EXIT_POLICIES["LEGACY_5_4"])
        runner = m.simulate_ladder(rows, m.ENTRY_POLICIES["IMMEDIATE"], m.EXIT_POLICIES["RUNNER_10_4"])
        self.assertEqual(len(legacy), 2)
        self.assertEqual(legacy[-1]["opportunity_index"], 2)
        self.assertEqual(len(runner), 1)  # never armed at +10, so no synthetic reset

    def test_report_has_no_auto_selection_or_orders(self):
        out = m.analyze([])
        self.assertFalse(out["automatic_selection"])
        self.assertTrue(out["holdout_report_only"])
        self.assertFalse(out["orders"])
        self.assertFalse(out["fees_included"])


if __name__ == "__main__":
    unittest.main()
