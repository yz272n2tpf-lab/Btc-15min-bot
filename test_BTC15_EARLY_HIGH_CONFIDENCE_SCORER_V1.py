#!/usr/bin/env python3
import unittest
import pandas as pd

import BTC15_EARLY_HIGH_CONFIDENCE_SCORER_V1 as m


def row(
    ticker="T", ts="2026-09-01T00:00:00Z", remaining=6.0,
    ask=.34, fair=.80, edge=.10, gap=30.0, preferred_num=1,
    current_side=1, final_side=1,
):
    return {
        "ticker":ticker,
        "snapshot_utc":pd.Timestamp(ts),
        "elapsed":15.0-remaining,
        "remaining":remaining,
        "current_side":current_side,
        "abs_dist_target":gap,
        "final_side":final_side,
        "preferred_side_num":preferred_num,
        "preferred_side":"UP" if preferred_num==1 else "DOWN",
        "preferred_fair":fair,
        "preferred_ask":ask,
        "preferred_bid":max(0,ask-.02),
        "edge":edge,
    }


class EarlyHighConfidenceScorerTests(unittest.TestCase):
    def test_protected_tier1_boundary(self):
        d=pd.DataFrame([
            row(ticker="ok",ask=.45,fair=.75,edge=.08,gap=25,remaining=2.0),
            row(ticker="price",ask=.451),
            row(ticker="fair",fair=.749),
            row(ticker="edge",edge=.079),
            row(ticker="gap",gap=24.99),
            row(ticker="early",remaining=10.01),
            row(ticker="late",remaining=1.99),
        ])
        keep=d.loc[m.tier1_mask(d),"ticker"].tolist()
        self.assertEqual(keep,["ok"])

    def test_same_row_candidates_are_subsets_of_first_tier1(self):
        d=pd.DataFrame([
            row(ticker="A",fair=.82),
            row(ticker="B",fair=.77,current_side=0),
            row(ticker="C",ask=.60,fair=.95,edge=.30,gap=100),
        ])
        base=m.first_tier1_rows(d)
        self.assertEqual(set(base.ticker),{"A","B"})
        for name in m.SAME_ROW_RULES:
            calls=m.same_row_calls(base,name)
            self.assertTrue(set(calls.ticker).issubset(set(base.ticker)))
            if len(calls):
                self.assertTrue(m.tier1_mask(calls).all())

    def test_fair80_is_exactly_predeclared_threshold(self):
        base=pd.DataFrame([row(ticker="A",fair=.7999),row(ticker="B",fair=.80)])
        calls=m.same_row_calls(base,"FAIR80")
        self.assertEqual(calls.ticker.tolist(),["B"])

    def test_current_side_requires_agreement(self):
        base=pd.DataFrame([
            row(ticker="A",preferred_num=1,current_side=1),
            row(ticker="B",preferred_num=1,current_side=0),
        ])
        calls=m.same_row_calls(base,"CURRENT_SIDE")
        self.assertEqual(calls.ticker.tolist(),["A"])

    def test_persistence_uses_later_protected_row_and_same_side(self):
        d=pd.DataFrame([
            row("A","2026-09-01T00:00:00Z",remaining=6,preferred_num=1),
            row("A","2026-09-01T00:00:45Z",remaining=5.25,preferred_num=1,ask=.36,fair=.81),
            row("B","2026-09-01T00:00:00Z",remaining=6,preferred_num=1),
            row("B","2026-09-01T00:00:45Z",remaining=5.25,preferred_num=0,ask=.36,fair=.81),
        ]).sort_values(["ticker","snapshot_utc"])
        base=m.first_tier1_rows(d)
        calls=m.confirmation_calls(d,base,False)
        self.assertEqual(calls.ticker.tolist(),["A"])
        self.assertAlmostEqual(float(calls.iloc[0].confirmation_delay_sec),45.0)
        self.assertTrue(m.tier1_mask(calls).all())

    def test_strengthening_rejects_weaker_confirmation(self):
        d=pd.DataFrame([
            row("A","2026-09-01T00:00:00Z",remaining=6,fair=.82,edge=.12),
            row("A","2026-09-01T00:00:45Z",remaining=5.25,fair=.81,edge=.11),
            row("B","2026-09-01T00:00:00Z",remaining=6,fair=.80,edge=.10),
            row("B","2026-09-01T00:00:45Z",remaining=5.25,fair=.82,edge=.12),
        ]).sort_values(["ticker","snapshot_utc"])
        base=m.first_tier1_rows(d)
        calls=m.confirmation_calls(d,base,True)
        self.assertEqual(calls.ticker.tolist(),["B"])

    def test_historical_gate_requires_all_prefrozen_conditions(self):
        good=pd.Series({
            "all_calls":15,"h1_calls":7,"h2_calls":8,
            "all_accuracy":.94,"h1_accuracy":1.0,"h2_accuracy":.90,
            "all_avg_ask":.40,"all_median_ask":.40,"all_avg_time":5.1,
        })
        self.assertTrue(m.gate(good))
        bad=good.copy();bad["h2_accuracy"]=.899
        self.assertFalse(m.gate(bad))


if __name__=="__main__":
    unittest.main()
