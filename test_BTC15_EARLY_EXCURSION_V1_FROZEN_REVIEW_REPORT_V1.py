#!/usr/bin/env python3
import unittest
import BTC15_EARLY_EXCURSION_V1_FROZEN_REVIEW_REPORT_V1 as r

def payload(*,eligible=13,calls=1,complete=1,sample_ready=False,hits=(1,1,1,1)):
    return {"version":"BTC15_EARLY_EXCURSION_FORWARD_V1","orders":False,"live":{"version":"BTC15_EARLY_EXCURSION_FORWARD_V1","status":"EARLY_EXCURSION_REVIEW_SAMPLE_READY" if sample_ready else "COLLECTING_EARLY_EXCURSION_FORWARD","coverage_universe_semantics":"FIRST_SEEN_BEFORE_EARLY_10M_WINDOW","fresh_start_semantics":"FIRST_POST_START_ROLLOVER","eligible_contracts":eligible,"excluded_late_n":0,"early_calls":calls,"early_coverage":None if not eligible else calls/eligible,"completed_early_excursions":complete,"avg_entry_ask":.43 if calls else None,"median_entry_ask":.43 if calls else None,"ideal_25_35c_n":0,"ideal_25_35c_rate":0.0 if calls else None,"avg_entry_minutes_left":3.29 if calls else None,"median_entry_minutes_left":3.29 if calls else None,"avg_mfe":.559 if complete else None,"median_mfe":.559 if complete else None,"avg_mae":-.01 if complete else None,"median_mae":-.01 if complete else None,"final_seen_after_early_n":0,"final_agreement_rate":None,"settled_early_n":1 if complete else 0,"settlement_same_side_rate_secondary":1.0 if complete else None,"sample_ready":sample_ready,"orders":False,"manual_execution_only":True,"production_behavior_changed":False,"early_thresholds_changed":False,**{f"hit_{n}c_n":v for n,v in zip((5,10,15,20),hits)},**{f"hit_{n}c_rate":None if not complete else v/complete for n,v in zip((5,10,15,20),hits)}}}

class ExcursionReviewTests(unittest.TestCase):
    def test_current_like_waits(self):
        z=r.build_report(payload());self.assertTrue(z["integrity"]["pass"]);self.assertEqual(z["frozen_gate"]["remaining_eligible"],17);self.assertEqual(z["frozen_gate"]["remaining_completed"],9)
    def test_ready_is_manual_only(self):
        z=r.build_report(payload(eligible=30,calls=12,complete=10,sample_ready=True,hits=(9,8,6,4)));self.assertEqual(z["status"],"EARLY_EXCURSION_V1_MANUAL_REVIEW_READY");self.assertTrue(z["frozen_gate"]["manual_review_ready"]);self.assertFalse(z["decision_controls"]["auto_promote_allowed"])
    def test_counts_without_collector_ready_wait(self):
        z=r.build_report(payload(eligible=30,calls=12,complete=10,sample_ready=False,hits=(9,8,6,4)));self.assertTrue(z["frozen_gate"]["counts_ready"]);self.assertFalse(z["frozen_gate"]["manual_review_ready"])
    def test_nested_target_hierarchy_is_required(self):
        p=payload(hits=(1,0,1,0));self.assertIn("nested_target_counts",r.build_report(p)["integrity"]["errors"])
    def test_target_rate_math_is_checked(self):
        p=payload();p["live"]["hit_10c_rate"]=0.0;self.assertIn("hit_10c_rate_math",r.build_report(p)["integrity"]["errors"])
    def test_coverage_and_ideal_math_checked(self):
        p=payload();p["live"]["early_coverage"]=.9;self.assertIn("coverage_math",r.build_report(p)["integrity"]["errors"])
        p2=payload();p2["live"]["ideal_25_35c_rate"]=1.0;self.assertIn("ideal_rate_math",r.build_report(p2)["integrity"]["errors"])
    def test_threshold_or_production_change_invalid(self):
        p=payload();p["live"]["early_thresholds_changed"]=True;self.assertIn("early_thresholds_changed",r.build_report(p)["integrity"]["errors"])
        p2=payload();p2["live"]["production_behavior_changed"]=True;self.assertIn("production_behavior_changed",r.build_report(p2)["integrity"]["errors"])
    def test_move_metrics_never_become_final_accuracy(self):
        z=r.build_report(payload());self.assertFalse(z["excursion"]["metric_is_final_accuracy"]);self.assertFalse(z["excursion"]["checkpoints_are_qualification_rules"]);self.assertFalse(z["downstream_context"]["settlement_is_success_definition"])
    def test_orders_invalid(self):
        p=payload();p["orders"]=True;self.assertIn("orders_not_false",r.build_report(p)["integrity"]["errors"])
    def test_render_preserves_utility_semantics(self):
        text=r.render_text(r.build_report(payload()));self.assertIn("MFE avg",text);self.assertIn("+5/+10/+15/+20",text);self.assertIn("not FINAL accuracy",text);self.assertIn("checkpoints not qualification rules",text)

if __name__=="__main__":unittest.main()
