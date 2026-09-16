#!/usr/bin/env python3
import unittest

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V14 as v14


class V14PresentationStabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = v14.build_dashboard()
        cls.text = cls.path.read_text(encoding="utf-8", errors="replace")

    def test_exact_btc_color_mutation_removed(self):
        self.assertNotIn(v14.OLD_BTC_COLOR_JS, self.text)
        self.assertIn(v14.NEW_BTC_COLOR_JS, self.text)

    def test_btc_numeric_cannot_pulse_or_color_flicker(self):
        self.assertIn('id="btc15-v14-stability-style"', self.text)
        self.assertIn("#btcPrice.data-pulse{animation:none!important;transition:none!important;}", self.text)
        self.assertIn("color:#f3f5f7!important", self.text)

    def test_tabular_numeric_stability(self):
        self.assertIn("font-variant-numeric:tabular-nums lining-nums!important", self.text)
        self.assertIn("#timerRemaining{min-inline-size:5.4ch", self.text)
        self.assertIn("#timerEnd{min-inline-size:8.2ch", self.text)
        self.assertIn("#finalConfidence{min-inline-size:5.4ch", self.text)

    def test_final_dynamic_copy_height_is_bounded(self):
        self.assertIn("#finalActionSub{", self.text)
        self.assertIn("height:2.8em!important", self.text)
        self.assertIn("-webkit-line-clamp:2!important", self.text)
        # Older render fix continues to own the full reason box.
        self.assertIn("#finalReason { min-height:4.2em !important; height:4.2em !important;", self.text)
        self.assertIn("-webkit-line-clamp:3 !important", self.text)

    def test_early_dynamic_copy_reserves_space(self):
        self.assertIn("#earlyEntry,#earlyFlow{", self.text)
        self.assertIn("min-height:2.8em", self.text)

    def test_single_visible_contract_timer_preserved(self):
        self.assertEqual(self.text.count('id="timerRemaining"'), 1)
        self.assertNotIn('<span>Contract time left</span>', self.text)
        self.assertIn("canonical_seconds_left", self.text)

    def test_v13_plain_language_and_v12_no_position_semantics_survive(self):
        for phrase in (
            "BTC15_COMBINED_SCALP_UI_V13_PLAIN_LANGUAGE",
            "BTC15_COMBINED_SCALP_UI_V12_NO_POSITION_TRACKING",
            "TRACKING ONLY · DON'T CHASE",
            "TRACKING ONLY · NO POSITION ASSUMED",
            "scalp_entry_price_filter_applied===false",
        ):
            self.assertIn(phrase, self.text)

    def test_safety_envelope_survives(self):
        for phrase in (
            "BTC15_COMBINED_STATE_BRIDGE_V6",
            "scalp_entry_guidance_is_display_only===true",
            "scalp_completed_display_actionable===false",
            "scalp_ended_unarmed_is_actionable_exit===false",
            "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS",
        ):
            self.assertIn(phrase, self.text)
        self.assertNotIn("flip_risk_percent", self.text)

    def test_v14_marker_unique(self):
        self.assertEqual(self.text.count(v14.MARKER), 1)
        self.assertEqual(self.text.count('id="btc15-v14-stability-style"'), 1)


if __name__ == "__main__":
    unittest.main()
