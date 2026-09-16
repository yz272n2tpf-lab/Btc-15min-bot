#!/usr/bin/env python3
from pathlib import Path
import tempfile
import unittest

import BTC15_DASHBOARD_V15_FIXTURE_PREVIEW as preview


class V15FixturePreviewTests(unittest.TestCase):
    def test_all_frozen_time_rollover_memory_and_context_fixtures_are_present(self):
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
                "CONTRACT_ROLLOVER_HISTORY",
                "SCALP_1_COMPLETE_SCAN_2",
                "SCALP_1_COMPLETE_SCALP_2_ACTIVE",
                "GOOD_ENTRY_TELEMETRY_BLIP_PROTECT",
                "DONT_CHASE_LATER_PROTECT",
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
                self.assertFalse(model["safety"]["historical_scalp_actionable"])
                self.assertFalse(model["safety"]["historical_scalp_can_change_current_signals"])
                self.assertFalse(model["safety"]["scalp_memory_actionable"])
                self.assertFalse(model["safety"]["scalp_memory_changes_current_signals"])
                self.assertFalse(model["safety"]["manual_position_confirmed"])
                self.assertFalse(model["safety"]["manual_entry_context_signal_filtering"])
                self.assertFalse(model["safety"]["manual_entry_context_signal_suppression"])

    def test_expensive_entry_fixture_is_tracking_only(self):
        model = preview.preview_models()["ACTIVE_CAUTION_ABOVE_50"]
        scalp = model["cards"]["SCALP_OPPORTUNITY"]
        self.assertTrue(scalp["tracking_only"])
        self.assertFalse(scalp["manual_entry_path_available"])
        self.assertIn("TRACKING ONLY", scalp["action"])
        self.assertIn("DON'T CHASE", scalp["primary"])
        self.assertEqual(scalp["rows"][-1]["value"], "MODEL TRACKING ONLY · NO POSITION ASSUMED")

    def test_good_entry_context_survives_protect_telemetry_blip(self):
        model = preview.preview_models()["GOOD_ENTRY_TELEMETRY_BLIP_PROTECT"]
        self.assertEqual(model["manual_entry_context"]["state"], "ACCEPTABLE_ENTRY_PATH")
        self.assertFalse(model["manual_entry_context"]["manual_position_confirmed"])
        scalp = model["cards"]["SCALP_OPPORTUNITY"]
        self.assertEqual(scalp["underlying_lifecycle_state"], "PROTECT")
        self.assertEqual(scalp["action"], "PROTECT PROFITS")
        self.assertEqual(scalp["primary"], "MOVE REACHED PROTECTION LEVEL")
        self.assertFalse(scalp["tracking_only"])
        self.assertTrue(scalp["manual_entry_path_available"])
        entry_row = next(r for r in scalp["rows"] if r["label"] == "Entry Price")
        self.assertEqual(entry_row["value"], "31¢")

    def test_dont_chase_context_stays_no_position_at_later_protect(self):
        model = preview.preview_models()["DONT_CHASE_LATER_PROTECT"]
        self.assertEqual(model["manual_entry_context"]["state"], "TRACKING_ONLY_NO_POSITION")
        self.assertFalse(model["manual_entry_context"]["manual_position_confirmed"])
        scalp = model["cards"]["SCALP_OPPORTUNITY"]
        self.assertEqual(scalp["underlying_lifecycle_state"], "PROTECT")
        self.assertTrue(scalp["tracking_only"])
        self.assertFalse(scalp["manual_entry_path_available"])
        self.assertIn("TRACKING ONLY", scalp["action"])
        self.assertNotIn("PROTECT PROFITS", scalp["action"])
        self.assertEqual(
            next(r for r in scalp["rows"] if r["label"] == "Profit Protection")["value"],
            "MODEL TRACKING ONLY · NO POSITION ASSUMED",
        )

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

    def test_contract_rollover_history_is_non_actionable_and_new_contract_wins(self):
        model = preview.preview_models()["CONTRACT_ROLLOVER_HISTORY"]
        hist = model["scalp_history_slot"]
        self.assertTrue(model["rollover"]["rollover_detected"])
        self.assertEqual(model["rollover"]["previous_contract"], "KXBTC15M-FIXTURE-OLD")
        self.assertEqual(model["rollover"]["current_contract"], "KXBTC15M-FIXTURE-NEW")
        self.assertEqual(model["contract"], "KXBTC15M-FIXTURE-NEW")
        self.assertTrue(hist["visible"])
        self.assertTrue(hist["historical_only"])
        self.assertFalse(hist["actionable"])
        self.assertEqual(hist["headline"], "#1 COMPLETE · PROTECTED EXIT")
        self.assertNotIn("EXIT NOW", hist["headline"])
        self.assertNotIn("PROTECT PROFITS", hist["headline"])
        self.assertFalse(hist["orders"])
        self.assertIsNone(hist["order_action"])
        self.assertEqual(model["cards"]["CONTRACT_TIME_LEFT"]["primary"], "14:59")
        self.assertEqual(model["cards"]["SCALP_OPPORTUNITY"]["action"], "WATCHING FOR SCALP")

    def test_same_contract_completed_memory_remains_while_scanning(self):
        model = preview.preview_models()["SCALP_1_COMPLETE_SCAN_2"]
        hist = model["scalp_history_slot"]
        self.assertFalse(model["rollover"]["rollover_detected"])
        self.assertTrue(hist["visible"])
        self.assertEqual(hist["headline"], "#1 COMPLETE · PROTECTED EXIT")
        self.assertIn("scanning for #2", hist["detail"].lower())
        self.assertFalse(hist["actionable"])
        scalp = model["cards"]["SCALP_OPPORTUNITY"]
        self.assertEqual(scalp["action"], "WATCHING FOR SCALP")
        self.assertEqual(scalp["primary"], "SCANNING FOR #2")

    def test_same_contract_completed_memory_remains_while_second_scalp_is_active(self):
        model = preview.preview_models()["SCALP_1_COMPLETE_SCALP_2_ACTIVE"]
        hist = model["scalp_history_slot"]
        scalp = model["cards"]["SCALP_OPPORTUNITY"]
        self.assertTrue(hist["visible"])
        self.assertEqual(hist["headline"], "#1 COMPLETE · PROTECTED EXIT")
        self.assertFalse(hist["actionable"])
        self.assertEqual(scalp["action"], "UP #2 · ENTRY AVAILABLE")
        self.assertEqual(scalp["underlying_lifecycle_state"], "ACTIVE")
        self.assertTrue(scalp["manual_entry_path_available"])
        self.assertTrue(model["presentation_integrity"]["ok"])

    def test_history_slot_is_reserved_even_when_hidden(self):
        for name, model in preview.preview_models().items():
            with self.subTest(name=name):
                self.assertTrue(model["layout"]["scalp_history_slot_reserved"])
                self.assertFalse(model["layout"]["scalp_history_slot_changes_core_card_order"])
                self.assertTrue(model["scalp_history_slot"]["historical_only"])
                self.assertFalse(model["scalp_history_slot"]["actionable"])

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
        self.assertIn("CONTRACT ROLLOVER HISTORY", text)
        self.assertIn("SCALP 1 COMPLETE SCAN 2", text)
        self.assertIn("SCALP 1 COMPLETE SCALP 2 ACTIVE", text)
        self.assertIn("GOOD ENTRY TELEMETRY BLIP PROTECT", text)
        self.assertIn("DONT CHASE LATER PROTECT", text)
        self.assertIn('id="historySlot"', text)

    def test_viewport_breakpoints_match_frozen_contract(self):
        text = preview.build_html()
        self.assertIn("@media(min-width:768px) and (max-width:1180px)", text)
        self.assertIn("@media(min-width:1181px)", text)
        self.assertIn('grid-template-areas:"final final" "early timer" "scalp scalp" "flip flip"', text)
        self.assertIn('grid-template-areas:"final early" "timer scalp" "flip flip"', text)
        self.assertIn("env(safe-area-inset-top)", text)
        self.assertIn("font-variant-numeric:tabular-nums", text)
        self.assertIn(".history-slot{min-height:58px", text)

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
