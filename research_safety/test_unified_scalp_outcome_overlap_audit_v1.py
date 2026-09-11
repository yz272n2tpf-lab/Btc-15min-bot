import unittest

from unified_scalp_outcome_overlap_audit_v1 import audit_lines, price_zone


def result(lane, ticker, entry, adverse, gain, t10, side="UP"):
    return (
        f"LEAD_V7 RESULT | lane {lane} | {ticker} | {side} | zone Z | style X | "
        f"entry {entry:.3f} | max_gain {gain:+.3f} | adverse {adverse:+.3f} | "
        f"to+5c {'None' if t10 is None else t10} | to+10c {'None' if t10 is None else t10}"
    )


class OutcomeOverlapAuditTests(unittest.TestCase):
    def test_rough_winner_proves_aggregate_adverse_non_separating(self):
        lines = [
            result("MOMENTUM_EXPANSION", "WIN", 0.25, -0.12, 0.11, 50),
            result("MOMENTUM_EXPANSION", "FAIL", 0.098, -0.009, 0.032, None),
        ]
        r = audit_lines(lines)
        self.assertEqual(r["aggregate_adverse_gate_assessment"], "NON_SEPARATING_COUNTEREXAMPLES_PRESENT")
        self.assertEqual(r["decision"]["aggregate_adverse_only_tightening"], "REJECT")
        self.assertEqual(r["decision"]["path_ordered_trap_tightening"], "MORE_DATA")

    def test_no_counterexample_does_not_invent_tightening(self):
        lines = [
            result("MOMENTUM_EXPANSION", "WIN", 0.25, -0.01, 0.15, 20),
            result("MOMENTUM_EXPANSION", "FAIL", 0.25, -0.10, 0.02, None),
        ]
        r = audit_lines(lines)
        self.assertEqual(r["aggregate_adverse_gate_assessment"], "NO_ORDERING_COUNTEREXAMPLE_IN_CURRENT_SAMPLE")
        self.assertEqual(r["decision"]["aggregate_adverse_only_tightening"], "MORE_DATA")

    def test_cheap_price_never_changes_evidence_standard(self):
        lines = [
            result("MOMENTUM_EXPANSION", "CHEAP", 0.035, -0.01, 0.12, 25),
            result("MOMENTUM_EXPANSION", "HIGH", 0.44, -0.01, 0.12, 25),
        ]
        r = audit_lines(lines)
        self.assertFalse(r["cheap_price_evidence_override"])
        self.assertEqual(r["price_zones"]["3_7C"]["evidence_standard"], "UNIFIED_SAME_STANDARD_ALL_PRICES")
        self.assertEqual(r["price_zones"]["30_45C"]["evidence_standard"], "UNIFIED_SAME_STANDARD_ALL_PRICES")

    def test_legacy_reversal_is_audit_only(self):
        lines = [
            result("ULTRA_CHEAP_REVERSAL", "OLD", 0.04, -0.01, 0.90, 10),
            result("MOMENTUM_EXPANSION", "CUR", 0.20, -0.01, 0.11, 30),
        ]
        r = audit_lines(lines)
        self.assertEqual(r["legacy_reversal_research_only"], 1)
        self.assertEqual(r["unified_results"], 1)
        self.assertEqual(r["legacy_ultra_cheap_graduation"], "REJECT")

    def test_unknown_lane_fails_closed(self):
        lines = [result("SOMETHING_NEW", "X", 0.20, -0.01, 0.11, 30)]
        r = audit_lines(lines)
        self.assertEqual(r["unknown_lane_results"], 1)

    def test_price_zone_edges(self):
        self.assertEqual(price_zone(0.03), "3_7C")
        self.assertEqual(price_zone(0.069), "3_7C")
        self.assertEqual(price_zone(0.07), "7_15C")
        self.assertEqual(price_zone(0.15), "15_30C")
        self.assertEqual(price_zone(0.30), "30_45C")
        self.assertEqual(price_zone(0.45), "30_45C")
        self.assertEqual(price_zone(0.029), "OUT_OF_RANGE")
        self.assertEqual(price_zone(0.451), "OUT_OF_RANGE")

    def test_production_and_threshold_guards_are_hard_off(self):
        r = audit_lines([result("MOMENTUM_EXPANSION", "CUR", 0.20, -0.01, 0.11, 30)])
        self.assertEqual(r["production_promotion"], "NOT_PERFORMED")
        self.assertFalse(r["qualification_thresholds_changed"])
        self.assertTrue(r["research_only"])
        self.assertTrue(r["signal_only"])


if __name__ == "__main__":
    unittest.main()
