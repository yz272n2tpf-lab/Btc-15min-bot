#!/usr/bin/env python3
from __future__ import annotations

import unittest

import btc15_scalp_blueprint_forward_v1 as m


def c(cid, t, side="UP", left="600", btc30="20", ask="0.30", contract="C1"):
    return {"record_type":"CANDIDATE","contract":contract,"candidate_id":cid,"timestamp_utc":t,"side":side,"seconds_left":left,"btc30":btc30,"entry_ask":ask}


def p(cid, t, e, gain):
    return {"record_type":"PATH","candidate_id":cid,"timestamp_utc":t,"elapsed_sec":str(e),"exec_gain":str(gain)}


def result(cid, contract="C1"):
    return {"record_type":"RESULT","contract":contract,"candidate_id":cid,"timestamp_utc":"2026-09-14T21:30:00Z"}


class BlueprintForwardTests(unittest.TestCase):
    def test_price_band_is_telemetry_only(self):
        self.assertEqual(m.price_band(.07), "<10c")
        self.assertEqual(m.price_band(.58), "45-60c")
        self.assertEqual(m.price_band(.78), "70-80c")
        self.assertEqual(m.price_band(.88), "80c+")

    def test_unlimited_serial_resets_after_exit(self):
        rows = []
        base = [
            ("a","2026-09-14T21:10:00Z","UP","0.07"),
            ("b","2026-09-14T21:10:20Z","DOWN","0.32"),
            ("c","2026-09-14T21:10:40Z","UP","0.58"),
            ("d","2026-09-14T21:11:00Z","DOWN","0.78"),
        ]
        for cid, t, side, ask in base:
            rows.append(c(cid,t,side=side,ask=ask))
            rows += [
                p(cid,t,1,.06),
                p(cid,t,2,.01),
                result(cid),
            ]
        out = m.build_serial_opportunities(rows)
        self.assertEqual([x["candidate_id"] for x in out], ["a","b","c","d"])
        self.assertEqual([x["opportunity_index"] for x in out], [1,2,3,4])

    def test_failed_unarmed_primary_blocks_reset_until_validated_rule_exists(self):
        rows = [
            c("a","2026-09-14T21:10:00Z"),
            p("a","2026-09-14T21:10:10Z",10,.02),
            p("a","2026-09-14T21:10:20Z",20,-.12),
            result("a"),
            c("b","2026-09-14T21:11:00Z",side="DOWN"),
            p("b","2026-09-14T21:11:05Z",5,.20),
            result("b"),
        ]
        out = m.build_serial_opportunities(rows)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["candidate_id"], "a")
        self.assertFalse(out[0]["armed_plus5"])

    def test_cutoff_excludes_old_candidate(self):
        rows = [
            c("old","2026-09-14T21:07:59Z"), result("old"),
            c("new","2026-09-14T21:08:01Z"), result("new"),
        ]
        self.assertEqual([x["candidate_id"] for x in m.forward_candidates(rows)], ["new"])

    def test_no_order_capability(self):
        self.assertEqual(m.VERSION, "BTC15_SCALP_BLUEPRINT_FORWARD_V1")
        self.assertGreaterEqual(m.MIN_REVIEW_OPPORTUNITIES, 1)


if __name__ == "__main__":
    unittest.main()
