#!/usr/bin/env python3
from __future__ import annotations

import unittest
from collections import defaultdict

import BTC15_SCALP_LADDER_RESEARCH_V1 as r


def c(cid, t, side="UP", left="600", btc30="20", ask="0.30", contract="C1"):
    return {"record_type":"CANDIDATE","contract":contract,"candidate_id":cid,"timestamp_utc":t,"side":side,"seconds_left":left,"btc30":btc30,"entry_ask":ask}


def p(cid, t, e, gain):
    return {"record_type":"PATH","candidate_id":cid,"timestamp_utc":t,"elapsed_sec":str(e),"exec_gain":str(gain)}


class ScalpLadderResearchTests(unittest.TestCase):
    def test_frozen_gate_has_no_price_filter(self):
        self.assertTrue(r.candidate_qualified(c("a","2026-01-01T00:00:00Z",ask="0.02")))
        self.assertTrue(r.candidate_qualified(c("b","2026-01-01T00:00:00Z",ask="0.92")))
        self.assertFalse(r.candidate_qualified(c("c","2026-01-01T00:00:00Z",left="119")))
        self.assertFalse(r.candidate_qualified(c("d","2026-01-01T00:00:00Z",btc30="14.99")))

    def test_secondary_only_after_primary_protected_exit(self):
        candidates = {"C1":[
            c("p1","2026-01-01T00:00:00Z"),
            c("overlap","2026-01-01T00:00:05Z",side="DOWN"),
            c("p2","2026-01-01T00:00:20Z",side="DOWN",ask="0.55"),
        ]}
        paths = defaultdict(list)
        # p1 arms at +6c, then exits at +1c after 5c giveback at 12s.
        paths["p1"] += [
            p("p1","2026-01-01T00:00:03Z",3,.06),
            p("p1","2026-01-01T00:00:12Z",12,.01),
        ]
        # overlap would be a valid raw candidate but arrived before p1 exit.
        paths["overlap"] += [p("overlap","2026-01-01T00:00:10Z",5,.20)]
        # p2 is after the primary exit and should become opportunity 2.
        paths["p2"] += [
            p("p2","2026-01-01T00:00:25Z",5,.10),
            p("p2","2026-01-01T00:00:35Z",15,.05),
        ]
        out = r.build_opportunity_ladder(candidates, paths, {"C1":"VALIDATION"})
        self.assertEqual([x["candidate_id"] for x in out],["p1","p2"])
        self.assertEqual([x["opportunity_index"] for x in out],[1,2])

    def test_no_secondary_until_primary_has_exit(self):
        candidates = {"C1":[c("p1","2026-01-01T00:00:00Z"),c("p2","2026-01-01T00:01:00Z",side="DOWN")]}
        paths = defaultdict(list)
        paths["p1"] += [p("p1","2026-01-01T00:00:10Z",10,.02),p("p1","2026-01-01T00:00:30Z",30,-.12)]
        paths["p2"] += [p("p2","2026-01-01T00:01:10Z",10,.20)]
        out = r.build_opportunity_ladder(candidates, paths, {"C1":"VALIDATION"})
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]["candidate_id"],"p1")

    def test_failed_primary_grid_records_recovery_risk(self):
        candidates = {"C1":[c("p1","2026-01-01T00:00:00Z")]}
        paths = defaultdict(list)
        # Never reaches +5c overall; crosses -5c after 20s and later improves to +4c.
        paths["p1"] += [
            p("p1","2026-01-01T00:00:10Z",10,-.02),
            p("p1","2026-01-01T00:00:20Z",20,-.06),
            p("p1","2026-01-01T00:00:40Z",40,.04),
        ]
        out = r.build_failed_primary_grid(candidates, paths, {"C1":"VALIDATION"})
        cell = next(x for x in out if x["adverse_trigger_cents"]==5.0 and x["min_elapsed_sec"]==20.0)
        self.assertFalse(cell["would_recover_to_plus5"])
        self.assertAlmostEqual(cell["best_gain_after_trigger"],.04)

    def test_armed_primary_excluded_from_failed_grid(self):
        candidates = {"C1":[c("p1","2026-01-01T00:00:00Z")]}
        paths = defaultdict(list)
        paths["p1"] += [p("p1","2026-01-01T00:00:10Z",10,-.08),p("p1","2026-01-01T00:00:30Z",30,.06)]
        out = r.build_failed_primary_grid(candidates, paths, {"C1":"VALIDATION"})
        self.assertEqual(out,[])


if __name__ == "__main__":
    unittest.main()
