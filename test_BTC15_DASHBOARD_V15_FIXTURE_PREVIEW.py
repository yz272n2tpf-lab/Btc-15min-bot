#!/usr/bin/env python3
from pathlib import Path
import tempfile
import unittest

import BTC15_DASHBOARD_V15_FIXTURE_PREVIEW as preview


class V15FixturePreviewTests(unittest.TestCase):
    def test_all_frozen_and_time_guard_fixtures_are_present(self):
        models = preview.preview_models()
        self.assertEqual(
            set(models),
            {
                "WAIT",
                "ACTIVE_IDEAL",
                "ACTIVE_CAUTION_ABOVE_50",
                "PROTECT_PULLBACK",
                "EXIT",
                "SCANNING_NEXT",
                "STALE_FAIL_CLOSED",
                "TIME_5M_CAUTION",
                "TIME_3M_GUARD",
                "ROLLOVER",
            },
        )

    def test_every_fixture_uses_frozen_card_order_and_no_orders(self):
        for name, model in preview.preview_models().items():
            with self.subTest(name=name):
                self.assertEqual(
                    model["card_order"],
                    ["FINAL_OUTCOME", "EARLY_OPPORTUNITY", "CONTRACT_TIME_LEFT", "SCALP_OPPORTUNITY", "FLIP_RISK"],
                )
                self.assertTrue(model["safety"]["manual_execution_only"])
                self.assertFalse(model["safety"]["orders"])
                self.assertIsNone(model["safety"]["order_action"])
                self.assertFalse(model["safety"]["numeric_flip_risk_visible"])
                self.assertFalse(model["safety"]["watch_warning_thresholds_visible"])
                self.assertFalse(model["safety"]["time_guardrail_signal_filtering"])
                self.assertFalse(model["safety"]["time_guardrail_signal_suppression"])

    def test_expensive_entry_fixture_is_tracking_only(self):
        model = preview.preview_models()["ACTIVE_CAUTION_ABOVE_50"]
        scalp = model["cards"]["SCALP_OPPORTUNITY"]
        self.assertTrue(scalp["tracking_only"])
        self.assertFalse(scalp["manual_entry_path_available"])
        self.assertIn("TRACKING ONLY", scalp["action"])
        self.assertIn("DON'T CHASE", scalp["primary"])
        self.assertEqual(scalp["rows"][-1]["value"], "MODEL TRACKING ONLY · NO POSITION ASSUMED")

    def test_time_guardrail_fixtures_use_single_timer_card(self):
        models = preview.preview_models()
        expectations = {
            "TIME_5M_CAUTION": ("5:00", "CAUTION_5M", "5M CAUTION"),
            "TIME_3M_GUARD": ("3:00", "GUARD_3M", "3M GUARD RAIL"),
            "ROLLOVER": ("0:00", "ROLLOVER", "NEXT CONTRACT SYNCING"),
        }
        for name, (clock, band, label) in expectations.items():
            with self.subTest(name=name):
                timer = models[name]["cards"]["CONTRACT_TIME_LEFT"]
                self.assertEqual(timer["primary"], clock)
                self.assertEqual(timer["visible_timer_count"], 1)
                self.assertEqual(timer["guardrail_band"], band)
                self.assertEqual(timer["status_label"], label)
                self.assertTrue(timer["presentation_only"])
                self.assertFalse(timer["signal_filtering"])
                self.assertFalse(timer["signal_suppression"])

    def test_preview_html_is_offline_and_has_no_order_or_network_path(self):
        text = preview.build_html()
        for forbidden in (
            "fetch(", "XMLHttpRequest", "WebSocket", "EventSource",
            "place_order", "create_order", "submit_order",
        ):
            self.assertNotIn(forbidden, text)
        self.assertIn("OFFLINE · FIXTURE DATA · NO ORDERS", text)
        self.assertIn("SIGNAL ONLY · MANUAL EXECUTION · FIXTURE PREVIEW · NO ORDERS", text)
        self.assertIn('type="application/json" id="fixtureData"', text)
        self.assertIn("5M CAUTION", text)
        self.assertIn("3M GUARD RAIL", text)
        self.assertIn("NEXT CONTRACT SYNCING", text)

    def test_viewport_breakpoints_match_frozen_contract(self):
        text = preview.build_html()
        self.assertIn("@media(min-width:768px) and (max-width:1180px)", text)
        self.assertIn("@media(min-width:1181px)", text)
        self.assertIn('grid-template-areas:"final final" "early timer" "scalp scalp" "flip flip"', text)
        self.assertIn('grid-template-areas:"final early" "timer scalp" "flip flip"', text)
        self.assertIn("env(safe-area-inset-top)", text)
        self.assertIn("font-variant-numeric:tabular-nums", text)

    def test_fixture_preview_keeps_flip_risk_non_numeric(self):
        models = preview.preview_models()
        for name, model in models.items():
            with self.subTest(name=name):
                flip = model["cards"]["FLIP_RISK"]
                self.assertEqual(flip["primary"], "NOT CALIBRATED")
                self.assertIsNone(flip["numeric_value"])
                self.assertFalse(flip["numeric_visible"])
        self.assertNotIn("flip_risk_percent", preview.build_html())

    def test_preview_file_builds_as_self_contained_html(self):
        with tempfile.TemporaryDirectory() as td:
            path = preview.build_preview(Path(td) / "preview.html")
            self.assertTrue(path.exists())
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("<!doctype html>"))
            self.assertIn("BTC 15 MIN · V15 FIXTURE PREVIEW", text)
            self.assertGreater(len(text), 5000)


if __name__ == "__main__":
    unittest.main()
