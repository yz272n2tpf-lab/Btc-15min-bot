import unittest

import BTC15_AUTHORITATIVE_SCOREBOARD_VIEWMODEL_V1 as m


class ViewModelTests(unittest.TestCase):
    def board(self):
        return {
            "sources": {
                "final": {"connected": True},
                "early": {"connected": True},
                "handoff": {"connected": True},
                "early_excursion": {"connected": True},
                "flip_risk": {"connected": True},
            },
            "final": {
                "eligible_contracts": 12,
                "settled_calls": 7,
                "directional_accuracy": 1.0,
                "final_only_coverage": 2/3,
                "avg_minutes_left": 5.28,
                "avg_locked_side_ask": .90,
                "ask_le_50c_n": 0,
                "sample_ready": False,
            },
            "early": {
                "eligible_contracts": 10,
                "settled_calls": 1,
                "early_only_coverage": .10,
                "avg_entry_ask": .43,
                "avg_minutes_left": 6.0,
                "ideal_25_35c_n": 0,
                "ask_le_50c_n": 1,
                "sample_ready": False,
            },
            "scalp": {
                "plus10_move_rate": .774,
                "completed_serial_opportunities": 115,
                "fresh_plus10_move_rate": .82,
            },
            "early_excursion": {
                "eligible_contracts": 1,
                "completed": 0,
                "sample_ready": False,
            },
            "handoff": {
                "eligible_contracts": 9,
                "handoffs": 0,
                "settled_final_locks": 5,
                "any_anchor_coverage": 2/3,
                "sample_ready": False,
            },
            "flip_risk": {
                "prediction_complete_contracts": 1,
                "settled_predictions": 6,
                "sample_ready": False,
                "display_value": .12,
            },
            "overall": {
                "certified_union_coverage": None,
                "certified_union_status": "NOT CERTIFIED",
            },
        }

    def test_final_progress_is_explicit(self):
        v = m.build_viewmodel(self.board())
        c = v["cards"]["final"]
        self.assertEqual(c["accuracy"], "100.0%")
        self.assertEqual(c["sample_progress"], "12/30 eligible · 7/12 settled locks")

    def test_flip_value_is_always_hidden(self):
        v = m.build_viewmodel(self.board())
        c = v["cards"]["flip_risk"]
        self.assertIsNone(c["value"])
        self.assertEqual(c["display"], "NOT CALIBRATED")
        self.assertIn("1/30 complete contracts", c["sample_progress"])

    def test_no_blended_accuracy(self):
        v = m.build_viewmodel(self.board())
        self.assertIsNone(v["cards"]["system"]["blended_accuracy"])
        self.assertIn("No single blended", v["cards"]["system"]["note"])

    def test_union_not_certified_is_preserved(self):
        v = m.build_viewmodel(self.board())
        self.assertEqual(v["cards"]["system"]["union_status"], "NOT CERTIFIED")
        self.assertEqual(v["cards"]["system"]["union_coverage"], "—")

    def test_scalp_is_labeled_movement_not_accuracy(self):
        v = m.build_viewmodel(self.board())
        c = v["cards"]["scalp"]
        self.assertEqual(c["plus10_move_rate"], "77.4%")
        self.assertIn("not FINAL accuracy", c["note"])

    def test_safety_flags_are_presentation_only_no_orders(self):
        v = m.build_viewmodel(self.board())
        self.assertTrue(v["safety"]["presentation_only"])
        self.assertFalse(v["safety"]["orders"])
        self.assertTrue(v["safety"]["numeric_flip_risk_hidden"])


if __name__ == "__main__":
    unittest.main()
