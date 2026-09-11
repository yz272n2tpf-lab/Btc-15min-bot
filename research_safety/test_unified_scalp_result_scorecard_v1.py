import unittest

from unified_scalp_result_scorecard_v1 import parse_result_line, score_lines

MOM = "LEAD_V7 RESULT | lane MOMENTUM_EXPANSION | T1 | UP | zone X | style BURST | entry 0.040 | max_gain +0.120 | adverse -0.020 | to+5c 10.0 | to+10c 20.0 | to+20c None | reprice+5c 10.0"
REV = "LEAD_V7 RESULT | lane ULTRA_CHEAP_REVERSAL | T2 | DOWN | zone X | style NO_EXPANSION | entry 0.040 | max_gain -0.001 | adverse -0.040 | to+5c None | to+10c None | to+20c None | reprice+5c None"
MOM2 = "LEAD_V7 RESULT | lane MOMENTUM_EXPANSION | T3 | DOWN | zone X | style EXPANSION | entry 0.400 | max_gain +0.150 | adverse -0.080 | to+5c 40.0 | to+10c 90.0 | to+20c None | reprice+5c 40.0"


class UnifiedScorecardTests(unittest.TestCase):
    def test_parse_momentum_result(self):
        p = parse_result_line(MOM)
        self.assertIsNotNone(p)
        self.assertEqual(p.entry, 0.04)
        self.assertEqual(p.t10, 20.0)

    def test_contract_summary_is_ignored(self):
        self.assertIsNone(parse_result_line("LEAD_V7 CONTRACT_SUMMARY | T1 | MOM n=10"))

    def test_legacy_reversal_is_counted_but_excluded(self):
        r = score_lines([MOM, REV])
        self.assertEqual(r["parsed_results"], 2)
        self.assertEqual(r["unified_results"], 1)
        self.assertEqual(r["legacy_reversal_research_only"], 1)
        self.assertEqual(r["qualification_guard"]["records"], 1)

    def test_cheap_unified_observation_uses_same_standard(self):
        r = score_lines([MOM])
        self.assertEqual(r["qualification_guard"]["graduation_eligible"], 1)
        self.assertEqual(r["qualification_guard"]["evidence_standard"], "UNIFIED_SCALP_EXPANSION")

    def test_speed_decomposition(self):
        r = score_lines([MOM, MOM2])
        self.assertEqual(r["speed_by_price_zone"]["3_7C"]["burst_0_30s"], 1)
        self.assertEqual(r["speed_by_price_zone"]["30_45C"]["expansion_31_180s"], 1)

    def test_architecture_keeps_one_path_and_rejects_separate_cheap_lane(self):
        r = score_lines([MOM])
        self.assertEqual(r["architecture"]["unified_scalp_expansion_path"], "KEEP")
        self.assertEqual(r["architecture"]["separate_ultra_cheap_graduation_path"], "REJECT")
        self.assertEqual(r["architecture"]["qualification_threshold_change"], "MORE_DATA")

    def test_production_promotion_is_never_performed(self):
        self.assertEqual(score_lines([MOM])["production_promotion"], "NOT_PERFORMED")

    def test_contract_balanced_rate(self):
        no_hit = MOM.replace("T1", "T4").replace("to+10c 20.0", "to+10c None")
        r = score_lines([MOM, no_hit, MOM2])
        self.assertEqual(r["independent_contracts"], 3)
        self.assertAlmostEqual(r["contract_balanced_hit10_rate"], 2/3)


if __name__ == "__main__":
    unittest.main()
