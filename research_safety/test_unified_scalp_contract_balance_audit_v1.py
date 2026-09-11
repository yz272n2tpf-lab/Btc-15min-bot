import unittest

from unified_scalp_contract_balance_audit_v1 import audit_lines, diagnostic_price_band


def result(lane, ticker, side, entry, t10="None"):
    style = "EXPANSION" if t10 != "None" else "NO_EXPANSION"
    return (
        f"LEAD_V7 RESULT | lane {lane} | {ticker} | {side} | zone ANY | style {style} | "
        f"entry {entry:.3f} | max_gain +0.120 | adverse -0.020 | "
        f"to+5c 10.0 | to+10c {t10} | to+20c None | reprice+5c 10.0"
    )


class ContractBalanceAuditTests(unittest.TestCase):
    def test_contract_balance_prevents_repeat_signals_from_looking_independent(self):
        report = audit_lines([
            result("MOMENTUM_EXPANSION", "A", "UP", .20, "10.0"),
            result("MOMENTUM_EXPANSION", "A", "UP", .21, "None"),
            result("MOMENTUM_EXPANSION", "B", "DOWN", .22, "10.0"),
        ])
        zone = report["by_price_band"]["15_30c"]
        self.assertEqual(zone["n"], 3)
        self.assertEqual(zone["independent_contracts"], 2)
        self.assertAlmostEqual(zone["raw_hit10_rate"], 2 / 3)
        self.assertAlmostEqual(zone["contract_balanced_hit10_rate"], .75)
        self.assertEqual(zone["independence_assessment"], "CORRELATED_REPEAT_EXPOSURE_PRESENT")
        self.assertEqual(report["decision"]["signal_count_only_zone_tightening"], "REJECT")

    def test_cheap_price_never_gets_evidence_override(self):
        report = audit_lines([
            result("MOMENTUM_EXPANSION", "CHEAP", "UP", .045, "10.0"),
        ])
        self.assertFalse(report["cheap_price_evidence_override"])
        self.assertTrue(report["price_bands_are_diagnostic_only"])
        self.assertEqual(report["by_price_band"]["3_7c"]["n"], 1)
        self.assertEqual(report["decision"]["zone_specific_threshold_change"], "MORE_DATA")
        self.assertEqual(report["decision"]["separate_ultra_cheap_graduation_path"], "REJECT")

    def test_legacy_reversal_is_audit_only_and_excluded_from_balance(self):
        report = audit_lines([
            result("ULTRA_CHEAP_REVERSAL", "OLD", "UP", .052, "48.0"),
            result("MOMENTUM_EXPANSION", "NOW", "UP", .099, "7.0"),
        ])
        self.assertEqual(report["legacy_reversal_research_only"], 1)
        self.assertEqual(report["unified_results"], 1)
        self.assertEqual(report["overall"]["n"], 1)
        self.assertEqual(report["by_price_band"]["7_15c"]["n"], 1)

    def test_unknown_lane_fails_closed_for_cli_preflight_signal(self):
        report = audit_lines([result("MYSTERY", "X", "UP", .20, "10.0")])
        self.assertEqual(report["unknown_lane_results"], 1)
        self.assertEqual(report["unified_results"], 0)

    def test_repeated_same_entry_is_exposed_not_deduplicated(self):
        report = audit_lines([
            result("MOMENTUM_EXPANSION", "A", "UP", .290, "26.0"),
            result("MOMENTUM_EXPANSION", "A", "UP", .290, "6.0"),
        ])
        zone = report["by_price_band"]["15_30c"]
        self.assertEqual(zone["n"], 2)
        self.assertEqual(zone["repeated_same_entry_observations"], 1)
        self.assertEqual(zone["max_signals_in_one_contract"], 2)

    def test_boundaries_are_diagnostic_only(self):
        self.assertEqual(diagnostic_price_band(.030), "3_7c")
        self.assertEqual(diagnostic_price_band(.070), "7_15c")
        self.assertEqual(diagnostic_price_band(.150), "15_30c")
        self.assertEqual(diagnostic_price_band(.300), "15_30c")
        self.assertEqual(diagnostic_price_band(.301), "30_45c")
        self.assertEqual(diagnostic_price_band(.450), "30_45c")
        self.assertEqual(diagnostic_price_band(.451), "outside_3_45c")

    def test_empty_audit_preserves_current_architecture(self):
        report = audit_lines([])
        self.assertEqual(report["unknown_lane_results"], 0)
        self.assertEqual(report["overall"]["n"], 0)
        self.assertEqual(report["decision"]["unified_scalp_expansion_path"], "KEEP")
        self.assertEqual(report["production_promotion"], "NOT_PERFORMED")
        self.assertFalse(report["qualification_thresholds_changed"])


if __name__ == "__main__":
    unittest.main()
