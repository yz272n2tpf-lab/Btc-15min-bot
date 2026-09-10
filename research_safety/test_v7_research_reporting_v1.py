import unittest

from v7_split_scorecard_v1 import build_scorecard, price_zone
from v7_freeze_gate_v1 import decide_lane
from v7_final_report_v1 import build_final_report

LOG = """
LEAD_V7 HEARTBEAT | KXBTC15M-A | 9.00m | BTC 77146.77 | BRTI 77153.26 | UP 0.076 | DOWN 0.925 | pending 1
LEAD_V7 HEARTBEAT | KXBTC15M-A | 8.49m | BTC 77122.27 | BRTI N/A | UP 0.078 | DOWN 0.923 | pending 1
LEAD_V7 HEARTBEAT | KXBTC15M-A | 8.00m | BTC 77126.78 | BRTI N/A | UP 0.054 | DOWN 0.947 | pending 1
LEAD_V7 HEARTBEAT | KXBTC15M-A | 7.50m | BTC 77125.21 | BRTI 77131.28 | UP 0.059 | DOWN 0.942 | pending 2
LEAD_V7 CANDIDATE | lane MOMENTUM_EXPANSION | KXBTC15M-A | DOWN | zone MOMENTUM_PREFERRED_7_30C | ask 0.120 | btc5 +22.54 | btc15 +44.21 | btc30 +27.77 | accel +7.80 | brti5 +30.35 | brti15 +46.88 | ask5 +0.000 | ask15 +0.000 | left 407s
LEAD_V7 RESULT | lane MOMENTUM_EXPANSION | KXBTC15M-A | DOWN | zone MOMENTUM_PREFERRED_7_30C | style EXPANSION | entry 0.120 | max_gain +0.300 | adverse -0.010 | to+5c 43.0 | to+10c 118.1 | to+20c 148.1 | reprice+5c 13.0
LEAD_V7 CANDIDATE | lane MOMENTUM_EXPANSION | KXBTC15M-A | DOWN | zone MOMENTUM_HIGH_STRONG | ask 0.350 | btc5 +26.03 | btc15 +26.06 | btc30 +17.49 | accel +17.34 | brti5 +22.66 | brti15 +14.39 | ask5 +0.000 | ask15 +0.000 | left 571s
LEAD_V7 RESULT | lane MOMENTUM_EXPANSION | KXBTC15M-A | DOWN | zone MOMENTUM_HIGH_STRONG | style BURST | entry 0.350 | max_gain +0.100 | adverse -0.150 | to+5c 27.0 | to+10c 27.0 | to+20c None | reprice+5c 27.0
LEAD_V7 CANDIDATE | lane ULTRA_CHEAP_REVERSAL | KXBTC15M-A | UP | zone REVERSAL_CONFIRMED_TURN_3_7C | ask 0.054 | btc5 +22.35 | btc15 +0.00 | btc30 +13.83 | accel +22.35 | brti5 +18.86 | brti15 +0.90 | ask5 +0.000 | ask15 +0.000 | left 467s
LEAD_V7 RESULT | lane ULTRA_CHEAP_REVERSAL | KXBTC15M-A | UP | zone REVERSAL_CONFIRMED_TURN_3_7C | style NO_EXPANSION | entry 0.054 | max_gain +0.020 | adverse -0.030 | to+5c None | to+10c None | to+20c None | reprice+5c None
LEAD_V7 CONTRACT_SUMMARY | KXBTC15M-A | MOM n=2 hit5=100.0% hit10=100.0% burst10=50.0% expand10=100.0% hit20=50.0% avgGain=+0.200 avgAdv=-0.080 | REV n=1 hit5=0.0% hit10=0.0% burst10=0.0% expand10=0.0% hit20=0.0% avgGain=+0.020 avgAdv=-0.030 | BRTI BRTI_RESILIENCE | samples=100 | primary_ok=80 (80.0%) | retry_recovered=15 | missing=0 | errors=20 | verifier_ok=0 | verifier_disagree=0 | diag_cache=25
"""

class ScorecardTests(unittest.TestCase):
    def test_price_zones(self):
        self.assertEqual(price_zone(.03), "3_7C")
        self.assertEqual(price_zone(.069), "3_7C")
        self.assertEqual(price_zone(.07), "7_15C")
        self.assertEqual(price_zone(.15), "15_30C")
        self.assertEqual(price_zone(.30), "15_30C")
        self.assertEqual(price_zone(.31), "30_45C")

    def test_lane_decomposition(self):
        s = build_scorecard(LOG)
        mom = s["lanes"]["MOMENTUM_EXPANSION"]
        rev = s["lanes"]["ULTRA_CHEAP_REVERSAL"]
        self.assertEqual(mom["resolved_count"], 2)
        self.assertEqual(rev["resolved_count"], 1)
        self.assertEqual(mom["price_zones"]["7_15C"]["n"], 1)
        self.assertEqual(mom["price_zones"]["30_45C"]["n"], 1)
        self.assertEqual(rev["price_zones"]["3_7C"]["n"], 1)

    def test_burst_expansion(self):
        m = build_scorecard(LOG)["lanes"]["MOMENTUM_EXPANSION"]["overall"]
        self.assertEqual(m["hit10_pct"], 100.0)
        self.assertEqual(m["burst10_pct"], 50.0)
        self.assertEqual(m["expand10_pct"], 100.0)
        self.assertEqual(m["hit20_pct"], 50.0)

    def test_brti_failure_classification(self):
        b = build_scorecard(LOG)["brti"]
        self.assertEqual(b["heartbeat_brti_ok_pct"], 50.0)
        self.assertEqual(b["max_consecutive_na_heartbeats"], 2)
        self.assertEqual(b["failure_class"], "PRIMARY_ERRORS_WITH_RETRY_RECOVERY")

class GateTests(unittest.TestCase):
    def test_no_policy_is_more_data(self):
        self.assertEqual(decide_lane({"n": 99, "hit10_pct": 100}, None)["decision"], "MORE_DATA")

    def test_more_data(self):
        p = {"min_n": 10, "keep": {"hit10_pct":{"min":80}}, "reject_floor":{"hit10_pct":{"min":50}}}
        self.assertEqual(decide_lane({"n":9,"hit10_pct":100}, p)["decision"], "MORE_DATA")

    def test_keep_tighten_reject(self):
        p = {"min_n": 2, "keep": {"hit10_pct":{"min":80}, "avg_adverse":{"min":-0.12}}, "reject_floor":{"hit10_pct":{"min":40}}}
        self.assertEqual(decide_lane({"n":2,"hit10_pct":90,"avg_adverse":-0.10}, p)["decision"], "KEEP")
        self.assertEqual(decide_lane({"n":2,"hit10_pct":70,"avg_adverse":-0.10}, p)["decision"], "TIGHTEN")
        self.assertEqual(decide_lane({"n":2,"hit10_pct":30,"avg_adverse":-0.10}, p)["decision"], "REJECT")

    def test_final_report_never_promotes(self):
        r = build_final_report(LOG, None)
        self.assertEqual(r["production_promotion"], "NOT_PERFORMED")
        self.assertTrue(all(v["decision"] == "MORE_DATA" for v in r["freeze_gate"]["lanes"].values()))

if __name__ == "__main__":
    unittest.main()
