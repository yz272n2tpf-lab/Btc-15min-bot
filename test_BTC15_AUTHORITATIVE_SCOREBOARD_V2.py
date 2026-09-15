import unittest

import BTC15_AUTHORITATIVE_SCOREBOARD_V2 as m


class ScoreboardV2Tests(unittest.TestCase):
    def test_handoff_native_names_map_exactly(self):
        p = {
            "version": "BTC15_EARLY_FINAL_HANDOFF_FORWARD_V1",
            "orders": False,
            "manual_execution_only": True,
            "summary": {
                "eligibility_complete_contracts": 9,
                "early_calls": 1,
                "final_locks": 6,
                "handoffs": 1,
                "early_only_contracts": 0,
                "final_only_contracts": 5,
                "no_anchor_contracts": 3,
                "any_signal_coverage": 6/9,
                "dual_anchor_coverage": 1/9,
                "handoff_side_agreement_rate": 1.0,
                "avg_early_to_final_gap_minutes": 2.5,
                "median_early_to_final_gap_minutes": 2.5,
                "settled_final_locks": 5,
                "final_accuracy": 1.0,
                "sample_ready": False,
            },
        }
        b = m.combine_scoreboard(handoff_payload=p)
        h = b["handoff"]
        self.assertEqual(h["final_calls"], 6)
        self.assertAlmostEqual(h["any_anchor_coverage"], 6/9)
        self.assertEqual(h["side_agreement_rate"], 1.0)
        self.assertEqual(h["avg_handoff_gap_minutes"], 2.5)
        self.assertEqual(h["final_only_contracts"], 5)
        self.assertEqual(h["final_accuracy"], 1.0)

    def test_excursion_native_names_map_exactly(self):
        p = {
            "version": "BTC15_EARLY_EXCURSION_FORWARD_V1",
            "orders": False,
            "manual_execution_only": True,
            "summary": {
                "eligible_contracts": 30,
                "early_calls": 10,
                "completed_early_excursions": 10,
                "early_coverage": 1/3,
                "avg_entry_ask": .34,
                "median_entry_ask": .33,
                "ideal_25_35c_n": 7,
                "ideal_25_35c_rate": .7,
                "avg_entry_minutes_left": 6.2,
                "median_entry_minutes_left": 6.0,
                "avg_mfe": .14,
                "median_mfe": .12,
                "avg_mae": -.025,
                "median_mae": -.02,
                "hit_5c_rate": .9,
                "hit_10c_rate": .8,
                "hit_15c_rate": .6,
                "hit_20c_rate": .4,
                "final_seen_after_early_n": 8,
                "final_agreement_rate": .75,
                "settlement_same_side_rate_secondary": .7,
                "sample_ready": True,
            },
        }
        b = m.combine_scoreboard(excursion_payload=p)
        x = b["early_excursion"]
        self.assertEqual(x["completed"], 10)
        self.assertEqual(x["plus10_rate"], .8)
        self.assertEqual(x["avg_entry_minutes_left"], 6.2)
        self.assertEqual(x["ideal_25_35c_n"], 7)
        self.assertEqual(x["final_agreement_rate"], .75)

    def test_early_secondary_native_name_maps(self):
        p = {
            "summary": {
                "eligibility_complete_contracts": 6,
                "early_calls": 1,
                "settled_early_calls": 1,
                "settlement_same_side_rate_secondary": 0.0,
            },
            "orders": False,
        }
        b = m.combine_scoreboard(early_payload=p)
        self.assertEqual(b["early"]["settlement_same_side_rate_secondary"], 0.0)

    def test_flip_settled_review_predictions_maps(self):
        p = {
            "summary": {
                "prediction_complete_contracts": 3,
                "settled_prediction_complete_contracts": 2,
                "settled_review_predictions": 12,
                "sample_ready": False,
                "gate_pass": False,
            },
            "orders": False,
        }
        b = m.combine_scoreboard(flip_payload=p)
        r = b["flip_risk"]
        self.assertEqual(r["prediction_complete_contracts"], 3)
        self.assertEqual(r["settled_predictions"], 12)
        self.assertEqual(r["settled_complete_contracts"], 2)

    def test_flip_gate_pass_still_does_not_show_number(self):
        p = {
            "summary": {
                "prediction_complete_contracts": 30,
                "settled_review_predictions": 240,
                "sample_ready": True,
                "decision_ready": True,
                "gate_pass": True,
                "brier_skill": .08,
                "weighted_abs_calibration_error": .03,
                "stay90_actual_stay": .93,
                "current_flip_risk": .07,
            },
            "orders": False,
        }
        b = m.combine_scoreboard(flip_payload=p, numeric_flip_user_facing_approved=True)
        r = b["flip_risk"]
        self.assertTrue(r["gate_pass"])
        self.assertFalse(r["numeric_probability_validated"])
        self.assertFalse(r["user_facing_numeric_allowed"])
        self.assertIsNone(r["display_value"])
        self.assertEqual(r["display_status"], "HIDDEN_UNTIL_VALIDATED")

    def test_union_certification_uses_native_handoff_and_only_when_ready(self):
        base = {
            "eligibility_complete_contracts": 30,
            "early_calls": 12,
            "final_locks": 20,
            "handoffs": 10,
            "any_signal_coverage": .90,
            "dual_anchor_coverage": 1/3,
        }
        p = {"summary": dict(base, sample_ready=False), "orders": False}
        b = m.combine_scoreboard(handoff_payload=p)
        self.assertIsNone(b["overall"]["certified_union_coverage"])
        p2 = {"summary": dict(base, sample_ready=True), "orders": False}
        b2 = m.combine_scoreboard(handoff_payload=p2)
        self.assertEqual(b2["overall"]["certified_union_coverage"], .90)

    def test_v2_keeps_v1_scalp_semantics(self):
        b = m.combine_scoreboard()
        self.assertEqual(b["version"], m.VERSION)
        self.assertEqual(b["scalp"]["metric_semantics"], "SCALP_MOVEMENT_RATE_NOT_FINAL_ACCURACY")
        self.assertAlmostEqual(b["scalp"]["plus10_move_rate"], .774)

    def test_orders_true_still_fails_closed(self):
        with self.assertRaises(ValueError):
            m.combine_scoreboard(handoff_payload={"orders": True})


if __name__ == "__main__":
    unittest.main()
