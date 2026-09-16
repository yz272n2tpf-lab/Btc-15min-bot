#!/usr/bin/env python3
from pathlib import Path
import tempfile
import unittest

import BTC15_DASHBOARD_V15_SEQUENCE_PREVIEW as preview
from btc15_dashboard_session_sequence_fixtures_v1 import SEQUENCES


class V15SessionSequencePreviewTests(unittest.TestCase):
    def test_all_session_sequences_are_embedded(self):
        text = preview.build_html()
        for name in (
            "ACCEPTABLE_STALE_RECOVERY",
            "TRACKING_STALE_RECOVERY",
            "PROTECT_REGRESSION_QUARANTINE",
            "CONTRACT_ROLLOVER",
            "SERIAL_HANDOFF",
        ):
            self.assertIn(name, text)
        self.assertIn('type="application/json" id="sequenceData"', text)

    def test_known_frame_transitions_match_session_engine(self):
        acceptable = SEQUENCES["ACCEPTABLE_STALE_RECOVERY"]
        self.assertIn("ENTRY AVAILABLE", acceptable[0]["scalp_action"])
        self.assertTrue(acceptable[1]["source_fail_closed"])
        self.assertTrue(acceptable[1]["scalp_action"].startswith("WAIT ·"))
        self.assertEqual(acceptable[2]["scalp_action"], "PROTECT PROFITS")
        self.assertEqual(acceptable[2]["entry_context"], "ACCEPTABLE_ENTRY_PATH")

        tracking = SEQUENCES["TRACKING_STALE_RECOVERY"]
        self.assertIn("TRACKING ONLY", tracking[2]["scalp_action"])
        self.assertEqual(tracking[2]["entry_context"], "TRACKING_ONLY_NO_POSITION")

        quarantine = SEQUENCES["PROTECT_REGRESSION_QUARANTINE"]
        self.assertTrue(quarantine[2]["scalp_quarantined"])
        self.assertEqual(quarantine[2]["timer"], "8:20")
        self.assertEqual(quarantine[2]["final_action"], "LOCK · UP")

        serial = SEQUENCES["SERIAL_HANDOFF"]
        self.assertEqual(serial[2]["opportunity_index"], 2)
        self.assertTrue(serial[2]["history_visible"])
        self.assertIn("#1 COMPLETE", serial[2]["history_headline"])

    def test_preview_is_fully_offline_and_orderless(self):
        text = preview.build_html()
        for forbidden in (
            "fetch(",
            "XMLHttpRequest",
            "WebSocket",
            "EventSource",
            "place_order",
            "create_order",
            "submit_order",
        ):
            self.assertNotIn(forbidden, text)
        self.assertIn("OFFLINE FIXTURES · FRAME-BY-FRAME · NO ORDERS", text)
        self.assertIn("SIGNAL ONLY · MANUAL EXECUTION · OFFLINE REPLAY · NO ORDERS", text)

    def test_every_frame_is_manual_execution_only(self):
        for sequence_name, frames in SEQUENCES.items():
            for frame in frames:
                with self.subTest(sequence=sequence_name, frame=frame["frame"]):
                    self.assertFalse(frame["manual_position_confirmed"])
                    self.assertFalse(frame["orders"])

    def test_preview_exposes_safety_diagnostics_without_signal_logic(self):
        text = preview.build_html()
        self.assertIn("SOURCE FAIL-CLOSED", text)
        self.assertIn("SCALP FRAME QUARANTINED", text)
        self.assertIn("MANUAL POSITION NOT CONFIRMED", text)
        self.assertIn("LAST COMPLETED SCALP · HISTORY ONLY", text)
        self.assertIn("Single canonical timer.", text)
        self.assertIn("font-variant-numeric:tabular-nums", text)
        self.assertIn("env(safe-area-inset-top)", text)

    def test_preview_file_builds_self_contained(self):
        with tempfile.TemporaryDirectory() as td:
            path = preview.build_preview(Path(td) / "sequence_preview.html")
            self.assertTrue(path.exists())
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("<!doctype html>"))
            self.assertIn("BTC 15 MIN · SESSION REPLAY", text)
            self.assertGreater(len(text), 5000)


if __name__ == "__main__":
    unittest.main()
