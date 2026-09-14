#!/usr/bin/env python3
from __future__ import annotations

import unittest

import btc15_scalp_ladder_shadow_state_v1 as shadow


def c(cid,t,side="UP",left="600",btc30="20",ask="0.30",contract="C1"):
    return {"record_type":"CANDIDATE","contract":contract,"candidate_id":cid,"timestamp_utc":t,"side":side,"seconds_left":left,"btc30":btc30,"entry_ask":ask}


def p(cid,t,e,g):
    return {"record_type":"PATH","candidate_id":cid,"timestamp_utc":t,"elapsed_sec":str(e),"exec_gain":str(g)}


def s(t="2026-01-01T00:00:30Z",contract="C1"):
    return {"record_type":"SNAPSHOT","contract":contract,"timestamp_utc":t,"seconds_left":"570"}


class ShadowStateTests(unittest.TestCase):
    def test_later_candidate_is_observe_only(self):
        rows=[
            s(),
            c("p1","2026-01-01T00:00:00Z"),
            p("p1","2026-01-01T00:00:03Z",3,.06),
            p("p1","2026-01-01T00:00:12Z",12,.01),
            c("p2","2026-01-01T00:00:20Z",side="DOWN",ask="0.55"),
            p("p2","2026-01-01T00:00:25Z",5,.12),
        ]
        out=shadow.build_shadow_ladder(rows)
        self.assertEqual(out["primary"]["candidate_id"],"p1")
        self.assertEqual(len(out["later_opportunities"]),1)
        self.assertEqual(out["later_opportunities"][0]["candidate_id"],"p2")
        self.assertFalse(out["later_opportunities"][0]["actionable"])
        self.assertFalse(out["later_opportunities_actionable"])
        self.assertFalse(out["orders"])

    def test_prearm_failure_is_telemetry_not_exit_rule(self):
        rows=[
            s(),c("p1","2026-01-01T00:00:00Z"),
            p("p1","2026-01-01T00:00:10Z",10,.02),
            p("p1","2026-01-01T00:00:30Z",30,-.12),
        ]
        out=shadow.build_shadow_ladder(rows)
        self.assertIsNotNone(out["prearm_failure_telemetry"])
        self.assertFalse(out["prearm_failure_telemetry"]["actionable_cut_rule"])
        self.assertEqual(out["later_opportunities"],[])
        self.assertFalse(out["orders"])

    def test_no_price_filter_inherited(self):
        rows=[s(),c("p1","2026-01-01T00:00:00Z",ask="0.91"),p("p1","2026-01-01T00:00:05Z",5,.01)]
        out=shadow.build_shadow_ladder(rows)
        self.assertEqual(out["primary"]["entry_ask"],.91)


if __name__=="__main__":unittest.main()
