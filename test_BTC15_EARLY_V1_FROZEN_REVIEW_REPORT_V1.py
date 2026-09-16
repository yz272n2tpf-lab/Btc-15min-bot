#!/usr/bin/env python3
import unittest
import BTC15_EARLY_V1_FROZEN_REVIEW_REPORT_V1 as r


def payload(*,eligible=22,calls=2,settled=2,same=1,sample_ready=False,asks_le50=2,ideal=0):
    return {"ok":True,"version":"BTC15_EARLY_FORWARD_SCORECARD_V1","orders":False,"manual_execution_only":True,"live":{"version":"BTC15_EARLY_FORWARD_SCORECARD_V1","status":"EARLY_CONFIRMATION_SAMPLE_READY" if sample_ready else "COLLECTING_EARLY_FORWARD","fresh_start_semantics":"FIRST_POST_START_ROLLOVER","coverage_universe_semantics":"FIRST_SEEN_BEFORE_EARLY_10M_ELIGIBILITY_WINDOW","early_eligibility_open_seconds_left":600.0,"eligibility_complete_contracts":eligible,"coverage_excluded_late_n":0,"early_calls":calls,"early_only_coverage":None if not eligible else calls/eligible,"settled_early_calls":settled,"settlement_same_side_n":same,"settlement_same_side_rate_secondary":None if not settled else same/settled,"avg_ask":.43 if calls else None,"median_ask":.43 if calls else None,"ask_le_50c_n":asks_le50,"ask_le_50c_rate":None if not calls else asks_le50/calls,"ask_25_35c_n":ideal,"ask_25_35c_rate":None if not calls else ideal/calls,"avg_minutes_left":3.29 if calls else None,"median_minutes_left":3.29 if calls else None,"avg_fair":.763 if calls else None,"avg_edge":.333 if calls else None,"sample_ready":sample_ready,"settlement_accuracy_is_secondary_not_final_authority":True,"protected_early_thresholds_changed":False,"price_filter_added":False,"production_behavior_changed":False,"numeric_flip_risk_validated":False,"manual_execution_only":True,"orders":False}}

class EarlyReviewTests(unittest.TestCase):
    def test_current_like_waits(self):
        z=r.build_report(payload()); self.assertTrue(z["integrity"]["pass"]); self.assertEqual(z["status"],"WAITING_FOR_FROZEN_GATE"); self.assertEqual(z["frozen_gate"]["remaining_eligible"],8); self.assertEqual(z["frozen_gate"]["remaining_settled"],10)
    def test_ready_is_manual_review_only(self):
        z=r.build_report(payload(eligible=30,calls=14,settled=12,same=10,sample_ready=True,asks_le50=14,ideal=6)); self.assertEqual(z["status"],"EARLY_V1_MANUAL_REVIEW_READY"); self.assertTrue(z["frozen_gate"]["manual_review_ready"]); self.assertFalse(z["decision_controls"]["auto_promote_allowed"])
    def test_counts_without_collector_ready_waits(self):
        z=r.build_report(payload(eligible=30,calls=14,settled=12,same=10,sample_ready=False,asks_le50=14,ideal=6)); self.assertTrue(z["frozen_gate"]["counts_ready"]); self.assertFalse(z["frozen_gate"]["manual_review_ready"])
    def test_wrong_version_invalid(self):
        p=payload(); p["version"]="OTHER"; p["live"]["version"]="OTHER"; self.assertIn("collector_version:OTHER",r.build_report(p)["integrity"]["errors"])
    def test_denominator_or_start_semantics_invalid(self):
        p=payload(); p["live"]["coverage_universe_semantics"]="BAD"; self.assertIn("coverage_semantics",r.build_report(p)["integrity"]["errors"])
        p2=payload(); p2["live"]["fresh_start_semantics"]="BAD"; self.assertIn("fresh_start_semantics",r.build_report(p2)["integrity"]["errors"])
    def test_threshold_price_filter_production_changes_invalid(self):
        for field,error in (("protected_early_thresholds_changed","protected_thresholds_changed"),("price_filter_added","price_filter_added"),("production_behavior_changed","production_behavior_changed")):
            p=payload(); p["live"][field]=True; self.assertIn(error,r.build_report(p)["integrity"]["errors"])
    def test_settlement_must_stay_secondary(self):
        p=payload(); p["live"]["settlement_accuracy_is_secondary_not_final_authority"]=False; self.assertIn("settlement_semantics",r.build_report(p)["integrity"]["errors"])
        self.assertFalse(r.build_report(payload())["secondary_direction"]["is_final_accuracy"])
    def test_math_mismatches_fail_closed(self):
        p=payload(); p["live"]["early_only_coverage"]=.9; self.assertIn("coverage_math",r.build_report(p)["integrity"]["errors"])
        p=payload(); p["live"]["settlement_same_side_rate_secondary"]=1.0; self.assertIn("settlement_rate_math",r.build_report(p)["integrity"]["errors"])
        p=payload(); p["live"]["ask_le_50c_rate"]=.2; self.assertIn("le50_rate_math",r.build_report(p)["integrity"]["errors"])
    def test_entry_band_counts_fail_closed(self):
        p=payload(calls=2,asks_le50=1,ideal=2); self.assertIn("entry_band_counts",r.build_report(p)["integrity"]["errors"])
    def test_orders_or_numeric_flip_invalid(self):
        p=payload(); p["orders"]=True; self.assertIn("orders_not_false",r.build_report(p)["integrity"]["errors"])
        p2=payload(); p2["live"]["numeric_flip_risk_validated"]=True; self.assertIn("numeric_flip_risk_unexpected",r.build_report(p2)["integrity"]["errors"])
    def test_render_labels_settlement_secondary(self):
        text=r.render_text(r.build_report(payload())); self.assertIn("Entry ask",text); self.assertIn("ideal 25–35¢",text); self.assertIn("SECONDARY, NOT FINAL ACCURACY",text); self.assertIn("no price filter",text)

if __name__=="__main__": unittest.main()
