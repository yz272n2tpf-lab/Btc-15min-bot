#!/usr/bin/env python3
import unittest
import BTC15_HANDOFF_V1_FROZEN_REVIEW_REPORT_V1 as r

def payload(*,eligible=21,early=1,final=12,both=0,settled=12,sample_ready=False):
    union=early+final-both; eo=early-both; fo=final-both; none=eligible-union
    return {"version":"BTC15_EARLY_FINAL_HANDOFF_FORWARD_V1","orders":False,"live":{"version":"BTC15_EARLY_FINAL_HANDOFF_FORWARD_V1","status":"HANDOFF_REVIEW_SAMPLE_READY" if sample_ready else "COLLECTING_HANDOFF_FORWARD","fresh_start_semantics":"FIRST_POST_START_ROLLOVER","coverage_universe_semantics":"FIRST_SEEN_BEFORE_EARLY_10M_ELIGIBILITY_WINDOW","eligibility_complete_contracts":eligible,"coverage_excluded_late_n":0,"early_calls":early,"final_locks":final,"handoffs":both,"early_only_contracts":eo,"final_only_contracts":fo,"no_anchor_contracts":none,"any_signal_coverage":None if not eligible else union/eligible,"early_coverage":None if not eligible else early/eligible,"final_coverage":None if not eligible else final/eligible,"dual_anchor_coverage":None if not eligible else both/eligible,"handoff_side_agreement_rate":None if not both else .8,"avg_early_to_final_gap_minutes":None if not both else 2.5,"median_early_to_final_gap_minutes":None if not both else 2.4,"avg_early_ask":.43 if early else None,"median_early_ask":.43 if early else None,"early_ideal_25_35c_n":0,"early_ideal_25_35c_rate":0.0 if early else None,"early_le_50c_n":early,"early_le_50c_rate":1.0 if early else None,"avg_final_ask":.90 if final else None,"median_final_ask":.92 if final else None,"final_le_50c_n":0,"final_le_50c_rate":0.0 if final else None,"avg_same_side_ask_change_early_to_final":None if not both else .40,"settled_final_locks":settled,"final_accuracy":1.0 if settled else None,"settled_early_calls":early,"early_same_side_as_settlement_rate_secondary":1.0 if early else None,"sample_ready":sample_ready,"review_gate":{"min_eligible_contracts":30,"min_handoffs":10,"min_settled_final":12},"protected_early_thresholds_changed":False,"protected_final_thresholds_changed":False,"auto_promotion":False,"orders":False,"manual_execution_only":True}}

class HandoffReviewTests(unittest.TestCase):
    def test_current_like_bottleneck_is_handoffs_and_eligible(self):
        z=r.build_report(payload());self.assertTrue(z["integrity"]["pass"]);self.assertEqual(z["frozen_gate"]["remaining_eligible"],9);self.assertEqual(z["frozen_gate"]["remaining_handoffs"],10);self.assertEqual(z["frozen_gate"]["remaining_settled_final"],0)
    def test_union_math_uses_true_overlap(self):
        z=r.build_report(payload(eligible=30,early=12,final=24,both=10,settled=16));self.assertEqual(z["common_universe"]["any_signal_count"],26);self.assertAlmostEqual(z["common_universe"]["any_signal_coverage"],26/30)
    def test_ready_certifies_only_common_universe(self):
        z=r.build_report(payload(eligible=30,early=14,final=27,both=11,settled=16,sample_ready=True));self.assertTrue(z["frozen_gate"]["manual_review_ready"]);self.assertTrue(z["common_universe"]["target_90pct_certified"]);self.assertFalse(z["decision_controls"]["auto_promote_allowed"])
    def test_counts_without_collector_ready_not_certified(self):
        z=r.build_report(payload(eligible=30,early=14,final=27,both=11,settled=16,sample_ready=False));self.assertFalse(z["common_universe"]["target_90pct_certified"]);self.assertFalse(z["frozen_gate"]["manual_review_ready"])
    def test_double_counted_union_fails(self):
        p=payload();p["live"]["any_signal_coverage"]=13/21;self.assertIn("union_coverage_math",r.build_report(p)["integrity"]["errors"])
    def test_partition_mismatch_fails(self):
        p=payload();p["live"]["no_anchor_contracts"]=0;self.assertIn("partition_math",r.build_report(p)["integrity"]["errors"])
    def test_fake_handoffs_fail_bounds(self):
        p=payload(early=1,final=12,both=2);self.assertIn("count_bounds",r.build_report(p)["integrity"]["errors"])
    def test_gate_or_threshold_drift_fails(self):
        p=payload();p["live"]["review_gate"]["min_handoffs"]=5;self.assertIn("review_gate_drift",r.build_report(p)["integrity"]["errors"])
        p2=payload();p2["live"]["protected_early_thresholds_changed"]=True;self.assertIn("early_thresholds_changed",r.build_report(p2)["integrity"]["errors"])
    def test_agreement_with_zero_handoffs_must_be_null(self):
        p=payload();p["live"]["handoff_side_agreement_rate"]=1.0;self.assertIn("agreement_should_be_null",r.build_report(p)["integrity"]["errors"])
    def test_render_forbids_added_coverages(self):
        text=r.render_text(r.build_report(payload()));self.assertIn("Common-universe any-signal coverage",text);self.assertIn("SECONDARY, NOT FINAL ACCURACY",text);self.assertIn("no added coverages",text)

if __name__=="__main__": unittest.main()
