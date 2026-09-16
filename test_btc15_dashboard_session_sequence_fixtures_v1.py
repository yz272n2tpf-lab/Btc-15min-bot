#!/usr/bin/env python3
import unittest

from btc15_dashboard_session_sequence_fixtures_v1 import SEQUENCES


class DashboardSessionSequenceFixturesV1Tests(unittest.TestCase):
    def test_expected_sequences_exist(self):
        self.assertEqual(
            set(SEQUENCES),
            {
                "ACCEPTABLE_STALE_RECOVERY",
                "TRACKING_STALE_RECOVERY",
                "PROTECT_REGRESSION_QUARANTINE",
                "CONTRACT_ROLLOVER",
                "SERIAL_HANDOFF",
            },
        )

    def test_acceptable_stale_recovery(self):
        seq = SEQUENCES["ACCEPTABLE_STALE_RECOVERY"]
        self.assertIn("ENTRY AVAILABLE", seq[0]["scalp_action"])
        self.assertTrue(seq[1]["source_fail_closed"])
        self.assertTrue(seq[1]["scalp_action"].startswith("WAIT ·"))
        self.assertEqual(seq[2]["scalp_action"], "PROTECT PROFITS")
        self.assertEqual(seq[2]["entry_context"], "ACCEPTABLE_ENTRY_PATH")

    def test_tracking_stale_recovery_never_becomes_protect_wording(self):
        seq = SEQUENCES["TRACKING_STALE_RECOVERY"]
        self.assertIn("TRACKING ONLY", seq[0]["scalp_action"])
        self.assertTrue(seq[1]["source_fail_closed"])
        self.assertIn("TRACKING ONLY", seq[2]["scalp_action"])
        self.assertNotEqual(seq[2]["scalp_action"], "PROTECT PROFITS")
        self.assertEqual(seq[2]["entry_context"], "TRACKING_ONLY_NO_POSITION")

    def test_regression_quarantine_keeps_scalp_but_advances_timer_and_final(self):
        seq = SEQUENCES["PROTECT_REGRESSION_QUARANTINE"]
        self.assertEqual(seq[1]["scalp_action"], "PROTECT PROFITS")
        self.assertTrue(seq[2]["scalp_quarantined"])
        self.assertEqual(seq[2]["quarantine_reason"], "SAME_OPPORTUNITY_STATE_REGRESSION")
        self.assertEqual(seq[2]["scalp_action"], "PROTECT PROFITS")
        self.assertEqual(seq[2]["timer"], "8:20")
        self.assertEqual(seq[2]["final_action"], "LOCK · UP")

    def test_contract_rollover_new_contract_wins(self):
        seq = SEQUENCES["CONTRACT_ROLLOVER"]
        self.assertEqual(seq[0]["contract"], "C1")
        self.assertEqual(seq[1]["contract"], "C2")
        self.assertEqual(seq[1]["timer"], "14:59")
        self.assertEqual(seq[1]["scalp_lifecycle"], "PASS")

    def test_serial_handoff_preserves_history_and_new_scalp_is_current(self):
        seq = SEQUENCES["SERIAL_HANDOFF"]
        self.assertEqual(seq[0]["scalp_lifecycle"], "EXIT")
        self.assertIn("WATCHING FOR SCALP", seq[1]["scalp_action"])
        self.assertTrue(seq[1]["history_visible"])
        self.assertIn("#1 COMPLETE", seq[1]["history_headline"])
        self.assertEqual(seq[2]["opportunity_index"], 2)
        self.assertIn("#2 · ENTRY AVAILABLE", seq[2]["scalp_action"])
        self.assertTrue(seq[2]["history_visible"])

    def test_all_sequence_frames_are_signal_only(self):
        for name, frames in SEQUENCES.items():
            for frame in frames:
                with self.subTest(sequence=name, frame=frame["frame"]):
                    self.assertFalse(frame["manual_position_confirmed"])
                    self.assertFalse(frame["orders"])


if __name__ == "__main__":
    unittest.main()
