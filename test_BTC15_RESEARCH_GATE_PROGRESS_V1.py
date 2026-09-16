import unittest

import BTC15_RESEARCH_GATE_PROGRESS_V1 as g


class GateProgressV1Tests(unittest.TestCase):
    def board(self):
        return {
            "final": {
                "eligible_contracts": 23,
                "settled_calls": 13,
                "sample_ready": False,
            },
            "early": {
                "eligible_contracts": 21,
                "settled_calls": 2,
                "sample_ready": False,
            },
            "handoff": {
                "eligible_contracts": 20,
                "handoffs": 0,
                "settled_final_locks": 11,
                "sample_ready": False,
            },
            "early_excursion": {
                "eligible_contracts": 10,
                "completed": 1,
                "sample_ready": False,
            },
            "flip_risk": {
                "prediction_complete_contracts": 3,
                "settled_predictions": 19,
                "sample_ready": False,
            },
        }

    def test_final_only_waits_on_eligible_once_settled_requirement_met(self):
        p = g.build_gate_progress(self.board())
        lane = p["lanes"]["final"]
        self.assertFalse(lane["review_ready"])
        self.assertEqual(lane["bottlenecks"], ["eligible contracts"])
        self.assertEqual(lane["requirements"][0]["remaining"], 7)
        self.assertTrue(lane["requirements"][1]["satisfied"])

    def test_early_reports_both_count_bottlenecks(self):
        p = g.build_gate_progress(self.board())
        lane = p["lanes"]["early"]
        self.assertEqual(lane["bottlenecks"], ["eligible contracts", "settled EARLY calls"])
        self.assertEqual(lane["requirements"][0]["remaining"], 9)
        self.assertEqual(lane["requirements"][1]["remaining"], 10)

    def test_handoff_zero_is_not_hidden_by_final_progress(self):
        p = g.build_gate_progress(self.board())
        lane = p["lanes"]["handoff"]
        self.assertIn("real EARLY→FINAL handoffs", lane["bottlenecks"])
        handoff_req = lane["requirements"][1]
        self.assertEqual(handoff_req["current"], 0)
        self.assertEqual(handoff_req["remaining"], 10)
        self.assertEqual(lane["count_progress"], 0.0)

    def test_flip_progress_is_count_progress_not_validation(self):
        p = g.build_gate_progress(self.board())
        lane = p["lanes"]["flip_risk"]
        self.assertFalse(lane["review_ready"])
        self.assertEqual(lane["semantics"], "FROZEN_COUNT_GATE_PROGRESS_NOT_ACCURACY_OR_ETA")
        self.assertEqual(lane["requirements"][0]["remaining"], 27)
        self.assertEqual(lane["requirements"][1]["remaining"], 221)

    def test_count_requirements_alone_do_not_override_collector_ready(self):
        b = self.board()
        b["final"].update({"eligible_contracts": 30, "settled_calls": 12, "sample_ready": False})
        lane = g.build_gate_progress(b)["lanes"]["final"]
        self.assertTrue(lane["count_requirements_satisfied"])
        self.assertFalse(lane["review_ready"])

    def test_ready_requires_counts_and_authoritative_sample_ready(self):
        b = self.board()
        b["final"].update({"eligible_contracts": 30, "settled_calls": 12, "sample_ready": True})
        lane = g.build_gate_progress(b)["lanes"]["final"]
        self.assertTrue(lane["review_ready"])
        self.assertEqual(lane["bottlenecks"], [])
        self.assertEqual(lane["count_progress"], 1.0)

    def test_over_target_counts_are_capped_not_redefined(self):
        b = self.board()
        b["final"].update({"eligible_contracts": 50, "settled_calls": 99, "sample_ready": True})
        lane = g.build_gate_progress(b)["lanes"]["final"]
        self.assertEqual(lane["count_progress"], 1.0)
        self.assertEqual(lane["requirements"][0]["target"], 30)
        self.assertEqual(lane["requirements"][1]["target"], 12)

    def test_missing_values_fail_closed_to_zero(self):
        p = g.build_gate_progress({})
        self.assertEqual(p["lanes"]["final"]["requirements"][0]["current"], 0)
        self.assertFalse(p["lanes"]["final"]["review_ready"])

    def test_no_eta_or_strategy_claims(self):
        p = g.build_gate_progress(self.board())
        self.assertFalse(p["safety"]["guesses_eta"])
        self.assertFalse(p["safety"]["changes_thresholds"])
        self.assertFalse(p["safety"]["orders"])

    def test_text_renderer_keeps_remaining_counts_visible(self):
        text = g.render_text(g.build_gate_progress(self.board()))
        self.assertIn("eligible contracts: 23/30 · remaining 7", text)
        self.assertIn("real EARLY→FINAL handoffs: 0/10 · remaining 10", text)
        self.assertIn("No ETA guesses", text)


if __name__ == "__main__":
    unittest.main()
