import unittest

from v7_contract_independence_audit_v1 import build_independence_audit


def result(ticker, lane="MOMENTUM_EXPANSION", t10="90"):
    zone = "MOMENTUM_PREFERRED_7_30C" if lane == "MOMENTUM_EXPANSION" else "REVERSAL_CONFIRMED_TURN_3_7C"
    style = "EXPANSION" if t10 != "None" else "NO_EXPANSION"
    entry = "0.120" if lane == "MOMENTUM_EXPANSION" else "0.050"
    return (
        f"LEAD_V7 RESULT | lane {lane} | {ticker} | UP | zone {zone} | style {style} | "
        f"entry {entry} | max_gain +0.200 | adverse -0.050 | to+5c 10 | "
        f"to+10c {t10} | to+20c None | reprice+5c 5"
    )


class ContractIndependenceAuditTests(unittest.TestCase):
    def test_cluster_concentration_is_quantified(self):
        log = "\n".join([result("A") for _ in range(5)] + [result("B")])
        lane = build_independence_audit(log)["lanes"]["MOMENTUM_EXPANSION"]
        self.assertEqual(lane["samples"], 6)
        self.assertEqual(lane["unique_contracts"], 2)
        self.assertEqual(lane["per_contract_samples"], {"A": 5, "B": 1})
        self.assertEqual(lane["repeated_samples_beyond_one_per_contract"], 4)
        self.assertEqual(lane["largest_contract_share_pct"], 83.33)
        self.assertEqual(lane["effective_contract_count"], 1.38)
        self.assertEqual(lane["concentration_warning"], "MAJORITY_FROM_ONE_CONTRACT")

    def test_balanced_metric_prevents_large_contract_from_dominating(self):
        log = "\n".join([result("A"), result("A"), result("A"), result("B", t10="None")])
        lane = build_independence_audit(log)["lanes"]["MOMENTUM_EXPANSION"]
        self.assertEqual(lane["sample_weighted_hit10_within_3m_pct"], 75.0)
        self.assertEqual(lane["contract_balanced_hit10_within_3m_pct"], 50.0)
        self.assertEqual(lane["weighted_vs_balanced_gap_pp"], 25.0)

    def test_results_over_180_seconds_do_not_count_as_three_minute_hits(self):
        log = "\n".join([result("A", t10="180"), result("B", t10="181")])
        lane = build_independence_audit(log)["lanes"]["MOMENTUM_EXPANSION"]
        self.assertEqual(lane["sample_weighted_hit10_within_3m_pct"], 50.0)
        self.assertEqual(lane["contract_balanced_hit10_within_3m_pct"], 50.0)

    def test_unique_contracts_have_full_effective_count(self):
        log = "\n".join([result("A"), result("B"), result("C")])
        lane = build_independence_audit(log)["lanes"]["MOMENTUM_EXPANSION"]
        self.assertEqual(lane["effective_contract_count"], 3.0)
        self.assertEqual(lane["effective_contract_ratio_pct"], 100.0)
        self.assertEqual(lane["concentration_warning"], "NO_MATERIAL_CONCENTRATION")

    def test_lanes_are_isolated(self):
        log = "\n".join([
            result("A"),
            result("A", lane="ULTRA_CHEAP_REVERSAL", t10="None"),
            result("B", lane="ULTRA_CHEAP_REVERSAL", t10="None"),
        ])
        audit = build_independence_audit(log)
        self.assertEqual(audit["lanes"]["MOMENTUM_EXPANSION"]["samples"], 1)
        self.assertEqual(audit["lanes"]["ULTRA_CHEAP_REVERSAL"]["samples"], 2)
        self.assertEqual(audit["lanes"]["ULTRA_CHEAP_REVERSAL"]["unique_contracts"], 2)

    def test_empty_input_is_safe_and_never_promotes(self):
        audit = build_independence_audit("")
        self.assertEqual(audit["result_count"], 0)
        self.assertEqual(audit["lanes"]["MOMENTUM_EXPANSION"]["concentration_warning"], "NO_DATA")
        self.assertEqual(audit["production_promotion"], "NOT_PERFORMED")


if __name__ == "__main__":
    unittest.main()
