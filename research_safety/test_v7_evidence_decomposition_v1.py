import unittest

from v7_evidence_decomposition_v1 import build_decomposition, price_zone


def result(ticker, lane="MOMENTUM_EXPANSION", zone="MOMENTUM_PREFERRED_7_30C", entry=.12,
           style="EXPANSION", t5="10", t10="90", t20="None", gain="+0.20", adverse="-0.05"):
    return (
        f"LEAD_V7 RESULT | lane {lane} | {ticker} | UP | zone {zone} | style {style} | "
        f"entry {entry:.3f} | max_gain {gain} | adverse {adverse} | to+5c {t5} | "
        f"to+10c {t10} | to+20c {t20} | reprice+5c 5.0"
    )


class DecompositionTests(unittest.TestCase):
    def test_price_zones(self):
        self.assertEqual(price_zone(.03), "3_7C")
        self.assertEqual(price_zone(.069), "3_7C")
        self.assertEqual(price_zone(.07), "7_15C")
        self.assertEqual(price_zone(.15), "15_30C")
        self.assertEqual(price_zone(.30), "15_30C")
        self.assertEqual(price_zone(.31), "30_45C")

    def test_speed_buckets_are_non_overlapping(self):
        log = "\n".join([
            result("A", t10="30"),
            result("B", t10="45"),
            result("C", t10="60"),
            result("D", t10="180"),
            result("E", style="NO_EXPANSION", t10="None"),
        ])
        o = build_decomposition(log)["lanes"]["MOMENTUM_EXPANSION"]["overall"]
        self.assertEqual(o["burst_0_30s_pct"], 20.0)
        self.assertEqual(o["fast_30_60s_pct"], 20.0)
        self.assertEqual(o["expansion_1_3m_pct"], 40.0)
        self.assertEqual(o["hit10_within_3m_pct"], 80.0)
        self.assertEqual(o["no_10c_within_3m_pct"], 20.0)

    def test_contract_clustering_is_exposed(self):
        log = "\n".join([result("A"), result("A", entry=.20), result("B", entry=.25)])
        lane = build_decomposition(log)["lanes"]["MOMENTUM_EXPANSION"]
        self.assertEqual(lane["unique_contracts"], 2)
        self.assertTrue(lane["repeated_within_contract"])
        self.assertEqual(lane["max_samples_in_one_contract"], 2)
        self.assertEqual(lane["largest_contract_share_pct"], 66.67)

    def test_price_and_collector_zone_decomposition(self):
        log = "\n".join([
            result("A", entry=.05, lane="ULTRA_CHEAP_REVERSAL", zone="REVERSAL_CONFIRMED_TURN_3_7C", style="NO_EXPANSION", t5="None", t10="None"),
            result("B", entry=.35, zone="MOMENTUM_HIGH_STRONG", style="BURST", t10="20"),
        ])
        d = build_decomposition(log)
        self.assertEqual(d["lanes"]["ULTRA_CHEAP_REVERSAL"]["price_zones"]["3_7C"]["n"], 1)
        self.assertEqual(d["lanes"]["MOMENTUM_EXPANSION"]["price_zones"]["30_45C"]["n"], 1)
        self.assertIn("MOMENTUM_HIGH_STRONG", d["lanes"]["MOMENTUM_EXPANSION"]["collector_zones"])

    def test_late_results_after_summary_are_attributed(self):
        log = "\n".join([
            result("A"),
            "LEAD_V7 CONTRACT_SUMMARY | A | MOM n=1 | REV n=0 | BRTI BRTI_RESILIENCE | samples=1 | primary_ok=1 (100.0%) | retry_recovered=0 | missing=0 | errors=0 | verifier_ok=0 | verifier_disagree=0 | diag_cache=0",
            result("A", lane="ULTRA_CHEAP_REVERSAL", zone="REVERSAL_CONFIRMED_TURN_3_7C", entry=.05, style="NO_EXPANSION", t5="None", t10="None"),
            result("B"),
        ])
        late = build_decomposition(log)["late_results_after_contract_summary"]
        self.assertEqual(late["count"], 1)
        self.assertEqual(late["by_contract"], {"A": 1})
        self.assertEqual(late["by_lane"], {"ULTRA_CHEAP_REVERSAL": 1})
        self.assertTrue(late["collector_summary_stale_risk"])

    def test_no_false_late_result_before_summary(self):
        log = "\n".join([result("A"), "LEAD_V7 CONTRACT_SUMMARY | A | MOM n=1 | REV n=0 | BRTI x"])
        self.assertEqual(build_decomposition(log)["late_results_after_contract_summary"]["count"], 0)

    def test_empty_input_is_safe_and_deterministic(self):
        a = build_decomposition("")
        b = build_decomposition("")
        self.assertEqual(a, b)
        self.assertEqual(a["result_count"], 0)
        self.assertEqual(a["lanes"]["MOMENTUM_EXPANSION"]["overall"]["n"], 0)
        self.assertIsNone(a["lanes"]["MOMENTUM_EXPANSION"]["largest_contract_share_pct"])


if __name__ == "__main__":
    unittest.main()
