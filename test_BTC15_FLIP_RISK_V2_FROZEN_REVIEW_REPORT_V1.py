#!/usr/bin/env python3
import unittest
import BTC15_FLIP_RISK_V2_FROZEN_REVIEW_REPORT_V1 as r


def payload(*, complete=3, settled_complete=3, preds=19, stay_n=19, stay_contracts=3,
            sample_ready=False, high_ready=False, forced=False, decision=False,
            gate_pass=False, status="COLLECTING_FUTURE_V2", pass_metrics=False):
    if pass_metrics:
        raw=.14; v2=.12; null=.18; skill=1-v2/null
        rel=[
            {"lo":0,"hi":.10,"n":80,"stated":.05,"actual":.04,"error":.01},
            {"lo":.10,"hi":.40,"n":80,"stated":.20,"actual":.18,"error":.02},
            {"lo":.40,"hi":1.0,"n":80,"stated":.60,"actual":.62,"error":.02},
        ]
        ece=(80*.01+80*.02+80*.02)/240
        max30=.02; rho=1.0; stay_actual=.925
        time=[{"minute":9,"n":30,"stated":.20,"actual":.25,"error":.05},
              {"minute":5,"n":30,"stated":.10,"actual":.12,"error":.02}]
        brier_ok=rel_ok=high_ok=time_ok=True
    else:
        raw=.003; v2=0.0; null=.15; skill=1.0
        rel=[]; ece=None; max30=None; rho=None
        stay_actual=1.0 if stay_n else None; time=[]
        brier_ok=True; rel_ok=False; high_ok=False; time_ok=True
    return {
        "version":"BTC15_DIRECT_BRTI_FLIP_RISK_FORWARD_V2",
        "orders":False,
        "live":{
            "version":"BTC15_DIRECT_BRTI_FLIP_RISK_FORWARD_V2",
            "status":status,
            "model_ready":True,
            "historical_train_snapshots":593,
            "historical_cal_snapshots":214,
            "historical_training_prior":.1788,
            "eligible_contracts":max(complete,18),
            "excluded_late_contracts":0,
            "ended_eligible_contracts":max(complete,17),
            "prediction_complete_contracts":complete,
            "settled_prediction_complete_contracts":settled_complete,
            "all_captured_predictions":max(preds,30),
            "settled_review_predictions":preds,
            "sample_ready":sample_ready,
            "gate_pass":gate_pass,
            "decision_ready":decision,
            "orders":False,
            "manual_execution_only":True,
            "production_changed":False,
            "numeric_flip_risk_user_facing_allowed":False,
            "raw_brier":raw,"v2_brier":v2,"null_brier":null,"brier_skill":skill,
            "reliability":rel,"weighted_abs_calibration_error":ece,
            "max_bin_error_n30":max30,"reliability_spearman":rho,
            "stay90_snapshots":stay_n,"stay90_contracts":stay_contracts,
            "stay90_actual_stay":stay_actual,"time_buckets":time,"time_ok":time_ok,
            "high_stay_ready":high_ready,"forced_high_stay_fail":forced,
            "brier_gate_ok":brier_ok,"reliability_gate_ok":rel_ok,
            "high_stay_gate_ok":high_ok,
        }
    }


class FlipV2ReviewTests(unittest.TestCase):
    def test_current_like_sample_is_collecting(self):
        z=r.build_report(payload())
        self.assertTrue(z["integrity"]["pass"])
        self.assertEqual(z["status"],"COLLECTING_FUTURE_V2")
        self.assertFalse(z["decision"]["gate_pass"])
        self.assertFalse(z["decision"]["numeric_user_facing_allowed"])

    def test_30_240_without_high_stay_is_not_pass(self):
        p=payload(complete=30,settled_complete=30,preds=240,stay_n=20,stay_contracts=6,
                  sample_ready=True,high_ready=False,forced=False,decision=False,
                  gate_pass=False,status="COLLECTING_HIGH_STAY_COHORT",pass_metrics=False)
        z=r.build_report(p)
        self.assertTrue(z["sample_progress"]["base_sample_ready"])
        self.assertEqual(z["status"],"COLLECTING_HIGH_STAY_COHORT")
        self.assertFalse(z["decision"]["decision_ready"])

    def test_forced_high_stay_fail_at_50(self):
        p=payload(complete=50,settled_complete=50,preds=400,stay_n=20,stay_contracts=6,
                  sample_ready=True,high_ready=False,forced=True,decision=True,
                  gate_pass=False,status="FUTURE_V2_REVIEW_SAMPLE_FAILED",pass_metrics=False)
        z=r.build_report(p)
        self.assertTrue(z["high_stay_progress"]["forced_fail_at_50_complete"])
        self.assertEqual(z["status"],"FUTURE_V2_REVIEW_SAMPLE_FAILED")
        self.assertFalse(z["decision"]["gate_pass"])

    def test_full_pass_is_manual_review_only(self):
        p=payload(complete=35,settled_complete=35,preds=240,stay_n=40,stay_contracts=10,
                  sample_ready=True,high_ready=True,forced=False,decision=True,
                  gate_pass=True,status="READY_FOR_NUMERIC_FLIP_RISK_MANUAL_REVIEW",pass_metrics=True)
        z=r.build_report(p)
        self.assertTrue(z["integrity"]["pass"])
        self.assertEqual(z["status"],"READY_FOR_NUMERIC_FLIP_RISK_MANUAL_REVIEW")
        self.assertTrue(z["decision"]["gate_pass"])
        self.assertFalse(z["decision"]["numeric_user_facing_allowed"])
        self.assertTrue(z["decision"]["manual_review_only_if_pass"])
        self.assertFalse(z["decision"]["auto_promote_allowed"])

    def test_fail_one_calibration_gate_fails_decision(self):
        p=payload(complete=35,settled_complete=35,preds=240,stay_n=40,stay_contracts=10,
                  sample_ready=True,high_ready=True,forced=False,decision=True,
                  gate_pass=False,status="FUTURE_V2_REVIEW_SAMPLE_FAILED",pass_metrics=True)
        # Consistent reliability rows with 8pp error in every populated bin.
        for row in p["live"]["reliability"]:
            row["actual"]=row["stated"]+.08
            row["error"]=.08
        p["live"]["weighted_abs_calibration_error"]=.08
        p["live"]["max_bin_error_n30"]=.08
        p["live"]["reliability_gate_ok"]=False
        z=r.build_report(p)
        self.assertTrue(z["integrity"]["pass"])
        self.assertEqual(z["status"],"FUTURE_V2_REVIEW_SAMPLE_FAILED")
        self.assertFalse(z["decision"]["gate_pass"])

    def test_training_snapshot_drift_fails_closed(self):
        p=payload();p["live"]["historical_train_snapshots"]=594
        z=r.build_report(p)
        self.assertIn("historical_train_snapshot_drift",z["integrity"]["errors"])

    def test_numeric_user_facing_exposure_fails_closed(self):
        p=payload();p["live"]["numeric_flip_risk_user_facing_allowed"]=True
        z=r.build_report(p)
        self.assertIn("numeric_flip_risk_exposed_early",z["integrity"]["errors"])

    def test_sample_ready_math_is_enforced(self):
        p=payload(complete=30,settled_complete=30,preds=240,sample_ready=False)
        z=r.build_report(p)
        self.assertIn("sample_ready_math",z["integrity"]["errors"])

    def test_decision_ready_math_is_enforced(self):
        p=payload(complete=30,settled_complete=30,preds=240,stay_n=30,stay_contracts=8,
                  sample_ready=True,high_ready=True,decision=False,status="COLLECTING_FUTURE_V2")
        z=r.build_report(p)
        self.assertIn("decision_ready_math",z["integrity"]["errors"])

    def test_reliability_row_math_is_checked(self):
        p=payload(complete=35,settled_complete=35,preds=240,stay_n=40,stay_contracts=10,
                  sample_ready=True,high_ready=True,decision=True,gate_pass=True,
                  status="READY_FOR_NUMERIC_FLIP_RISK_MANUAL_REVIEW",pass_metrics=True)
        p["live"]["reliability"][0]["error"]=.09
        z=r.build_report(p)
        self.assertIn("reliability_row_math",z["integrity"]["errors"])

    def test_brier_skill_math_is_checked(self):
        p=payload();p["live"]["brier_skill"]=.2
        z=r.build_report(p)
        self.assertIn("brier_skill_math",z["integrity"]["errors"])

    def test_time_bucket_math_and_gate_are_checked(self):
        p=payload(complete=35,settled_complete=35,preds=240,stay_n=40,stay_contracts=10,
                  sample_ready=True,high_ready=True,decision=True,gate_pass=True,
                  status="READY_FOR_NUMERIC_FLIP_RISK_MANUAL_REVIEW",pass_metrics=True)
        p["live"]["time_buckets"][0]["error"]=.01
        z=r.build_report(p)
        self.assertIn("time_bucket_math",z["integrity"]["errors"])

    def test_orders_or_production_change_fail_closed(self):
        p=payload();p["orders"]=True
        self.assertIn("orders_not_false",r.build_report(p)["integrity"]["errors"])
        p2=payload();p2["live"]["production_changed"]=True
        self.assertIn("production_changed",r.build_report(p2)["integrity"]["errors"])

    def test_render_keeps_numeric_risk_hidden(self):
        text=r.render_text(r.build_report(payload()))
        self.assertIn("Numeric Flip Risk remains HIDDEN",text)
        self.assertIn("manual review only",text)
        self.assertIn("no same-sample retune",text)
        self.assertIn("no auto-promotion",text)


if __name__=="__main__":
    unittest.main()
