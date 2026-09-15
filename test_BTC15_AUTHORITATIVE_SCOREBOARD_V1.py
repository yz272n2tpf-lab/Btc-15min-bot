import unittest

import BTC15_AUTHORITATIVE_SCOREBOARD_V1 as m


class ScoreboardV1Tests(unittest.TestCase):
    def final_payload(self):
        return {
            "version": "BTC15_FINAL_FORWARD_SCORECARD_V4",
            "orders": False,
            "manual_execution_only": True,
            "watchdog": {"healthy": True, "observer_restarts": 0},
            "live": {
                "status": "COLLECTING_LIVE_FORWARD",
                "eligibility_complete_contracts": 9,
                "lock_calls": 6,
                "settled_lock_calls": 6,
                "qualified_accuracy": 1.0,
                "final_only_coverage": 6/9,
                "avg_minutes_left": 4.66,
                "median_minutes_left": 4.80,
                "avg_preferred_ask": .918,
                "median_preferred_ask": .931,
                "ask_le_50c_n": 0,
                "ask_le_50c_rate": 0.0,
                "sample_ready": False,
                "orders": False,
                "manual_execution_only": True,
            },
        }

    def early_payload(self):
        return {
            "version": "BTC15_EARLY_FORWARD_SCORECARD_V1",
            "orders": False,
            "manual_execution_only": True,
            "summary": {
                "eligibility_complete_contracts": 6,
                "early_calls": 1,
                "settled_early_calls": 1,
                "early_only_coverage": 1/6,
                "avg_ask": .43,
                "median_ask": .43,
                "ask_le_50c_n": 1,
                "ideal_25_35c_n": 0,
                "avg_minutes_left": 6.0,
                "settlement_same_side_rate": 0.0,
                "sample_ready": False,
            },
        }

    def test_final_accuracy_stays_final_only(self):
        b = m.combine_scoreboard(final_payload=self.final_payload())
        self.assertEqual(b["final"]["directional_accuracy"], 1.0)
        self.assertIsNone(b["overall"]["system_accuracy"])
        self.assertEqual(b["overall"]["system_accuracy_status"], "NOT A VALID SINGLE METRIC")

    def test_separate_early_and_final_never_create_union(self):
        b = m.combine_scoreboard(final_payload=self.final_payload(), early_payload=self.early_payload())
        self.assertIsNone(b["overall"]["certified_union_coverage"])
        self.assertEqual(b["overall"]["certified_union_status"], "NOT CERTIFIED")

    def test_only_ready_common_universe_can_certify_union(self):
        handoff = {
            "version": "BTC15_EARLY_FINAL_HANDOFF_FORWARD_V1",
            "summary": {
                "eligibility_complete_contracts": 30,
                "early_calls": 12,
                "final_calls": 20,
                "handoffs": 10,
                "union_coverage": .90,
                "dual_anchor_coverage": 10/30,
                "sample_ready": True,
            },
            "orders": False,
            "manual_execution_only": True,
        }
        b = m.combine_scoreboard(handoff_payload=handoff)
        self.assertEqual(b["overall"]["certified_union_coverage"], .90)
        self.assertEqual(b["overall"]["certified_union_status"], "CERTIFIED_FROM_COMMON_UNIVERSE")

    def test_scalp_is_never_labeled_final_accuracy(self):
        b = m.combine_scoreboard()
        self.assertEqual(b["scalp"]["metric_semantics"], "SCALP_MOVEMENT_RATE_NOT_FINAL_ACCURACY")
        self.assertAlmostEqual(b["scalp"]["plus10_move_rate"], .774)
        text = m.render_text(b)
        self.assertIn("movement rate, NOT FINAL accuracy", text)

    def test_flip_numeric_hidden_until_all_three_conditions(self):
        p = {
            "summary": {
                "complete_contracts": 30,
                "settled_preds": 240,
                "ready": True,
                "numeric_flip_risk_validated": True,
                "current_flip_risk": .12,
            },
            "orders": False,
            "manual_execution_only": True,
        }
        b = m.combine_scoreboard(flip_payload=p, numeric_flip_user_facing_approved=False)
        self.assertFalse(b["flip_risk"]["user_facing_numeric_allowed"])
        self.assertIsNone(b["flip_risk"]["display_value"])
        b2 = m.combine_scoreboard(flip_payload=p, numeric_flip_user_facing_approved=True)
        self.assertTrue(b2["flip_risk"]["user_facing_numeric_allowed"])
        self.assertEqual(b2["flip_risk"]["display_value"], .12)

    def test_flip_hidden_if_not_validated_even_when_ready(self):
        p = {"summary": {"ready": True, "numeric_flip_risk_validated": False, "current_flip_risk": .08}}
        b = m.combine_scoreboard(flip_payload=p, numeric_flip_user_facing_approved=True)
        self.assertEqual(b["flip_risk"]["display_status"], "HIDDEN_UNTIL_VALIDATED")
        self.assertIsNone(b["flip_risk"]["display_value"])

    def test_orders_true_fails_closed(self):
        with self.assertRaises(ValueError):
            m.combine_scoreboard(final_payload={"orders": True})

    def test_missing_sources_are_explicit(self):
        b = m.combine_scoreboard()
        self.assertFalse(b["sources"]["final"]["connected"])
        self.assertEqual(b["sources"]["final"]["status"], "NOT CONNECTED")

    def test_excursion_metrics_remain_utility_metrics(self):
        x = {
            "summary": {
                "eligible_contracts": 30,
                "early_calls": 10,
                "complete": 10,
                "avg_entry_ask": .34,
                "avg_mfe": .16,
                "avg_mae": -.03,
                "plus5_rate": .9,
                "plus10_rate": .8,
                "plus15_rate": .6,
                "plus20_rate": .4,
                "ready": True,
            },
            "orders": False,
        }
        b = m.combine_scoreboard(excursion_payload=x)
        self.assertEqual(b["early_excursion"]["plus10_rate"], .8)
        self.assertIn("BID_BASED_TRADABLE_EXCURSION", b["early_excursion"]["metric_semantics"])
        self.assertIsNone(b["overall"]["system_accuracy"])

    def test_render_preserves_one_command_style_and_separations(self):
        b = m.combine_scoreboard(final_payload=self.final_payload(), early_payload=self.early_payload())
        text = m.render_text(b)
        self.assertIn("ONE-COMMAND BTC 15M AUTHORITATIVE SCOREBOARD", text)
        self.assertIn("FINAL", text)
        self.assertIn("EARLY", text)
        self.assertIn("SCALP", text)
        self.assertIn("FLIP RISK", text)
        self.assertIn(">=90% union-coverage claim: NOT CERTIFIED", text)
        self.assertIn("No orders", text)


if __name__ == "__main__":
    unittest.main()
